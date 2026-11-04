package ru.neurostenographer.app

import androidx.test.platform.app.InstrumentationRegistry
import android.os.Debug
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import ru.neurostenographer.core.PcmWav
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

/** Opt-in model comparison on identical audio and diarization windows. */
class AsrHeadProbeTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(1024 * 1024)
            while (true) {
                val size = input.read(buffer)
                if (size < 0) break
                digest.update(buffer, 0, size)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    @Test fun compareAsrHeads(): Unit = runBlocking {
        val assets = instrumentation.context.assets
        val selected = (InstrumentationRegistry.getArguments().getString("heads") ?: "a0,a1,a2,a3")
            .split(',').toSet()
        require(selected.isNotEmpty() && selected.all { it in setOf("a0", "a1", "a2", "a3") })
        val candidate = File(context.filesDir, "asr-e2e")
        val candidateModel = File(candidate, "model.int8.onnx")
        val candidateTokens = File(candidate, "tokens.txt")
        if ("a1" in selected) {
            assertEquals(224_893_668L, candidateModel.length())
            assertEquals("784d77aaa7a0899a247e72c71d667792087ee4dec985db1f57961767a5f6014f", sha256(candidateModel))
            assertEquals("142de7570b3de5b3035ce111a89c228e80e6085273731d944093ddf24fa539cd", sha256(candidateTokens))
        }
        val rnnt = File(context.filesDir, "asr-rnnt")
        val rnntEncoder = File(rnnt, "encoder.int8.onnx")
        val rnntHashes = mapOf(
            "encoder.int8.onnx" to "aa4e9bd1d8f1b30534c0b56d743970be53fd102dba639c2b1cc06e2aa898ada0",
            "decoder.onnx" to "ea08443676485385c0dd31d938233bffaed6e52d47d84844c9b568589f1c9b27",
            "joiner.onnx" to "ade116563dbf66e503b0994efab6b5861412743e52bf31c39fc3fffa3783d5d1",
            "tokens.txt" to "39abae20e692998290c574e606f11a9edef2902a1995463fcff63d1490cf22b7")
        if ("a2" in selected) {
            assertEquals(224_571_327L, rnntEncoder.length())
            for ((name, hash) in rnntHashes) assertEquals(hash, sha256(File(rnnt, name)))
        }
        val rnntV3 = File(context.filesDir, "asr-rnnt-v3")
        if ("a3" in selected) {
            val hashes = mapOf(
                "encoder.int8.onnx" to "0ec54e5f130a91c0f228d21795ede10b31c992a1f73e45dcd827e843a71a9b50",
                "decoder.onnx" to "5d1cfef155d8e07f213bd2f3229b5f6c5c29355c7fa5c1b9eb62cb1925725254",
                "joiner.onnx" to "fd1d02f45c2ad3d6b67cc149811ad794ab4b020ed49a0a9e2790a8619d1cddd8",
                "tokens.txt" to "17cc514451bcceac9c280068c71502f8448f99e9fb1456b8d0761651fd0392f2")
            for ((name, hash) in hashes) assertEquals(hash, sha256(File(rnntV3, name)))
        }

        val baseline = assets.open("gigaam-v3.zip").use { AsrModelStore(context).install(it) }
        val c0 = assets.open("diarization.zip").use { DiarizationModelStore(context).install(it) }
        val c2 = assets.open("nemotron.zip").use { NemotronDiarization.install(context.filesDir, it) }
        val plan = assets.open("nemotron-bench/plan.tsv").bufferedReader().readLines()
            .filter { it.isNotBlank() }
        val rows = JSONArray()
        val evidence = File(context.filesDir, "asr-head-evidence.json")
        for (line in plan) {
            val id = line.substringBefore('\t')
            val bytes = assets.open("nemotron-bench/$id.wav").use { it.readBytes() }
            val audioSha = MessageDigest.getInstance("SHA-256").digest(bytes)
                .joinToString("") { "%02x".format(it) }
            val audio = bytes.inputStream().use { PcmWav.read(it) }
            for (backend in listOf(NemotronBackend.C0, NemotronBackend.C2)) {
                val diarization = IsolatedDiarization.process(context, audio,
                    if (backend == NemotronBackend.C0) c0 else c2, backend = backend)
                for ((head, model) in listOf("a0" to baseline, "a1" to candidate,
                    "a2" to rnnt, "a3" to rnntV3).filter { it.first in selected }) {
                    val sampling = AtomicBoolean(true)
                    val peakPss = AtomicLong(0)
                    val sampler = Thread {
                        while (sampling.get()) {
                            peakPss.accumulateAndGet(Debug.getPss()) { a, b -> maxOf(a, b) }
                            Thread.sleep(25)
                        }
                    }.apply { start() }
                    val started = System.nanoTime()
                    val result = try {
                        OfflineAsr.transcribe(audio, model, turns = diarization.turns,
                            speechWindows = diarization.windows)
                    } finally {
                        sampling.set(false)
                        sampler.join()
                    }
                    val segments = JSONArray(result.segments.map { segment ->
                        JSONObject().put("start_ms", segment.startMs).put("end_ms", segment.endMs)
                            .put("speaker_id", segment.speakerId ?: JSONObject.NULL)
                            .put("text", segment.text)
                    })
                    rows.put(JSONObject().put("case", id).put("backend", backend).put("head", head)
                        .put("audio_sha256", audioSha).put("audio_ms", audio.durationMs)
                        .put("decoded_windows", result.decodedWindows)
                        .put("asr_load_ms", result.loadMs).put("asr_decode_ms", result.decodeMs)
                        .put("asr_wall_ms", (System.nanoTime() - started) / 1_000_000)
                        .put("peak_app_pss_kb", peakPss.get())
                        .put("segments", segments))
                    evidence.writeText(JSONObject().put("runs", rows).toString())
                }
            }
        }
        assertEquals(plan.size * 2 * selected.size, rows.length())
    }
}
