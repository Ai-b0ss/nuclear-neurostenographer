package ru.neurostenographer.app

import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import ru.neurostenographer.core.PcmWav
import ru.neurostenographer.core.DiarizationTimeline
import ru.neurostenographer.core.AudioWindow
import java.io.File
import java.security.MessageDigest

/** Paired C2 boundary policies on frozen Russian text cases. */
class C2PaddingAsrProbeTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext

    @Test fun compareBaseAndPadded(): Unit = runBlocking {
        val assets = instrumentation.context.assets
        val experiment = InstrumentationRegistry.getArguments().getString("experiment") ?: "threshold"
        require(experiment in setOf("threshold", "all_windows", "silero_gaps"))
        require(experiment != "silero_gaps" || BuildConfig.NATIVE_ASR_CANDIDATE)
        val c2 = assets.open("nemotron.zip").use { NemotronDiarization.install(context.filesDir, it) }
        val asr = assets.open("gigaam-v3.zip").use { AsrModelStore(context).install(it) }
        val cases = listOf(
            "nemotron-bench" to "aba", "nemotron-bench" to "holdout",
            "nemotron-bench" to "ivkond-2clean", "nemotron-bench" to "ivkond-2overlap",
            "nemotron-bench" to "ivkond-3overlap", "nemotron-bench" to "ivkond-4overlap",
            *Array(4) { "asr-holdout" to "acted-holdout-$it" })
        val runs = JSONArray()
        val evidence = File(context.filesDir, when (experiment) {
            "threshold" -> "c2-padding-asr-evidence.json"
            "all_windows" -> "c2-all-windows-evidence.json"
            else -> "c2-silero-gaps-evidence.json"
        })
        val vadModel = if (experiment == "silero_gaps") File(context.filesDir, "silero_vad.onnx").also { file ->
            val bytes = assets.open("silero_vad.onnx").use { it.readBytes() }
            check(MessageDigest.getInstance("SHA-256").digest(bytes)
                .joinToString("") { "%02x".format(it) } ==
                "9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6")
            file.writeBytes(bytes)
        } else null
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
            else if (experiment == "all_windows") listOf("pad150" to padded,
                "all_windows" to padded.copy(windows =
                    DiarizationTimeline.windows(padded.turns, audio.durationMs)))
            else listOf("pad150" to padded) + listOf(0.35f, 0.5f, 0.65f).map { threshold ->
                val vad = NativeVadProbe.detect(audio.samples, vadModel!!.absolutePath, threshold)
                check(vad.size % 2 == 0)
                val gaps = vad.toList().chunked(2).map { AudioWindow(it[0], it[1]) }
                val extra = sileroOnlyGaps(gaps, padded.windows, audio.durationMs)
                "silero_${(threshold * 100).toInt()}" to padded.copy(
                    windows = (padded.windows + extra).sortedBy { it.startMs })
            }
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
                    .put("windows", JSONArray(windows.map { JSONArray(listOf(it.startMs, it.endMs)) }))
                    .put("asr_load_ms", output.loadMs).put("asr_decode_ms", output.decodeMs)
                    .put("segments", segments))
                evidence.writeText(JSONObject().put("runs", runs).toString())
            }
        }
        assertEquals(cases.size * if (experiment == "silero_gaps") 4 else 2, runs.length())
    }

    private fun sileroOnlyGaps(vad: List<AudioWindow>, base: List<AudioWindow>, audioMs: Long): List<AudioWindow> {
        val result = mutableListOf<AudioWindow>()
        for (region in vad) {
            var cursor = region.startMs.coerceIn(0, audioMs)
            val stop = region.endMs.coerceIn(0, audioMs)
            for (window in base) {
                if (window.endMs <= cursor || window.startMs >= stop) continue
                if (window.startMs - cursor >= 300) result += AudioWindow(cursor, window.startMs)
                cursor = maxOf(cursor, window.endMs)
            }
            if (stop - cursor >= 300) result += AudioWindow(cursor, stop)
        }
        return result.sortedBy { it.startMs }.fold(mutableListOf()) { merged, next ->
            val last = merged.lastOrNull()
            if (last != null && next.startMs <= last.endMs) merged[merged.lastIndex] =
                AudioWindow(last.startMs, maxOf(last.endMs, next.endMs))
            else merged += next
            merged
        }
    }
}
