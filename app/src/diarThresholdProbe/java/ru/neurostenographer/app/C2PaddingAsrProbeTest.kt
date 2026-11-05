package ru.neurostenographer.app

import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import ru.neurostenographer.core.PcmWav
import ru.neurostenographer.core.DiarizationTimeline
import java.io.File
import java.security.MessageDigest

/** Paired C2 boundary policies on frozen Russian text cases. */
class C2PaddingAsrProbeTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext

    @Test fun compareBaseAndPadded(): Unit = runBlocking {
        val assets = instrumentation.context.assets
        val experiment = InstrumentationRegistry.getArguments().getString("experiment") ?: "threshold"
        require(experiment in setOf("threshold", "all_windows"))
        val c2 = assets.open("nemotron.zip").use { NemotronDiarization.install(context.filesDir, it) }
        val asr = assets.open("gigaam-v3.zip").use { AsrModelStore(context).install(it) }
        val cases = listOf(
            "nemotron-bench" to "aba", "nemotron-bench" to "holdout",
            "nemotron-bench" to "ivkond-2clean", "nemotron-bench" to "ivkond-2overlap",
            "nemotron-bench" to "ivkond-3overlap", "nemotron-bench" to "ivkond-4overlap",
            *Array(4) { "asr-holdout" to "acted-holdout-$it" })
        val runs = JSONArray()
        val evidence = File(context.filesDir, if (experiment == "threshold")
            "c2-padding-asr-evidence.json" else "c2-all-windows-evidence.json")
        for ((suite, name) in cases) {
            val bytes = assets.open("$suite/$name.wav").use { it.readBytes() }
            val hash = MessageDigest.getInstance("SHA-256").digest(bytes)
                .joinToString("") { "%02x".format(it) }
            val audio = bytes.inputStream().use { PcmWav.read(it) }
            val current = NemotronDiarization.process(audio, c2, activityThreshold = 0f)
            val padded = C2BoundaryPadding.apply(current, audio.durationMs, 150)
            val modes = if (experiment == "threshold") listOf(
                "pad150" to padded,
                "threshold_minus_0_25" to C2BoundaryPadding.apply(
                    NemotronDiarization.process(audio, c2, activityThreshold = -0.25f), audio.durationMs, 150))
            else listOf("pad150" to padded,
                "all_windows" to padded.copy(windows =
                    DiarizationTimeline.windows(padded.turns, audio.durationMs)))
            for ((mode, diarization) in modes) {
                val windows = C2WindowMerge.apply(diarization.windows, diarization.turns)
                val output = OfflineAsr.transcribe(audio, asr, turns = diarization.turns,
                    speechWindows = windows)
                val segments = JSONArray(output.segments.map { segment ->
                    JSONObject().put("start_ms", segment.startMs).put("end_ms", segment.endMs)
                        .put("speaker_id", segment.speakerId ?: JSONObject.NULL)
                        .put("text", segment.text)
                })
                runs.put(JSONObject().put("suite", suite).put("case", name).put("mode", mode)
                    .put("audio_sha256", hash).put("audio_ms", audio.durationMs)
                    .put("asr_load_ms", output.loadMs).put("asr_decode_ms", output.decodeMs)
                    .put("segments", segments))
                evidence.writeText(JSONObject().put("runs", runs).toString())
            }
        }
        assertEquals(cases.size * 2, runs.length())
    }
}
