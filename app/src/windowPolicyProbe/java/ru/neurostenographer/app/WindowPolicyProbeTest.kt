package ru.neurostenographer.app

import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import ru.neurostenographer.core.DiarizationTimeline
import ru.neurostenographer.core.PcmWav
import java.io.File
import java.security.MessageDigest

/** Exploratory quality/cost comparison; never changes the product window policy. */
class WindowPolicyProbeTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext

    @Test fun speechOnlyVersusAllGaps(): Unit = runBlocking {
        val assets = instrumentation.context.assets
        val c0 = assets.open("diarization.zip").use { DiarizationModelStore(context).install(it) }
        val c2 = assets.open("nemotron.zip").use { NemotronDiarization.install(context.filesDir, it) }
        val asr = assets.open("gigaam-v3.zip").use { AsrModelStore(context).install(it) }
        val plan = assets.open("nemotron-bench/plan.tsv").bufferedReader().readLines()
            .filter { it.isNotBlank() }
        val rows = JSONArray()
        val evidence = File(context.filesDir, "window-policy-evidence.json")
        for (line in plan) {
            val id = line.substringBefore('\t')
            val bytes = assets.open("nemotron-bench/$id.wav").use { it.readBytes() }
            val sha = MessageDigest.getInstance("SHA-256").digest(bytes)
                .joinToString("") { "%02x".format(it) }
            val audio = bytes.inputStream().use { PcmWav.read(it) }
            for (backend in listOf(NemotronBackend.C0, NemotronBackend.C2)) {
                val diarization = IsolatedDiarization.process(context, audio,
                    if (backend == NemotronBackend.C0) c0 else c2, backend = backend)
                val policies = listOf(
                    "speech_only" to diarization.windows,
                    "all_gaps" to DiarizationTimeline.windows(diarization.turns, audio.durationMs))
                for ((policy, windows) in policies) {
                    val started = System.nanoTime()
                    val result = OfflineAsr.transcribe(audio, asr, turns = diarization.turns,
                        speechWindows = windows)
                    val segments = JSONArray(result.segments.map { segment ->
                        JSONObject().put("start_ms", segment.startMs).put("end_ms", segment.endMs)
                            .put("speaker_id", segment.speakerId ?: JSONObject.NULL)
                            .put("text", segment.text)
                    })
                    rows.put(JSONObject().put("case", id).put("backend", backend).put("policy", policy)
                        .put("audio_sha256", sha).put("audio_ms", audio.durationMs)
                        .put("input_window_ms", windows.sumOf { it.endMs - it.startMs })
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
