package ru.neurostenographer.app

import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import ru.neurostenographer.core.PcmWav
import java.io.File
import java.security.MessageDigest

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

    @Test fun compareCtcHeads(): Unit = runBlocking {
        val assets = instrumentation.context.assets
        val candidate = File(context.filesDir, "asr-e2e")
        val candidateModel = File(candidate, "model.int8.onnx")
        val candidateTokens = File(candidate, "tokens.txt")
        assertEquals(224_893_668L, candidateModel.length())
        assertEquals("784d77aaa7a0899a247e72c71d667792087ee4dec985db1f57961767a5f6014f", sha256(candidateModel))
        assertEquals("142de7570b3de5b3035ce111a89c228e80e6085273731d944093ddf24fa539cd", sha256(candidateTokens))

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
                for ((head, model) in listOf("a0" to baseline, "a1" to candidate)) {
                    val started = System.nanoTime()
                    val result = OfflineAsr.transcribe(audio, model, turns = diarization.turns,
                        speechWindows = diarization.windows)
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
                        .put("segments", segments))
                    evidence.writeText(JSONObject().put("runs", rows).toString())
                }
            }
        }
        assertEquals(plan.size * 4, rows.length())
    }
}
