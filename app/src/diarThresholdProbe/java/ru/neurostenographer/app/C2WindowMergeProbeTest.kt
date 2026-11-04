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

/** Research only: join nearby same-speaker ASR windows after C2's promoted 150 ms padding. */
class C2WindowMergeProbeTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext

    @Test fun compareMergePolicies(): Unit = runBlocking {
        val assets = instrumentation.context.assets
        val c2 = assets.open("nemotron.zip").use { NemotronDiarization.install(context.filesDir, it) }
        val asr = assets.open("gigaam-v3.zip").use { AsrModelStore(context).install(it) }
        val caseSet = InstrumentationRegistry.getArguments().getString("caseSet") ?: "development"
        val development = listOf("nemotron-bench" to "aba", "nemotron-bench" to "holdout",
            "nemotron-bench" to "ivkond-2clean", "nemotron-bench" to "ivkond-2overlap",
            "nemotron-bench" to "ivkond-3overlap", "nemotron-bench" to "ivkond-4overlap",
            *Array(4) { "asr-holdout" to "acted-holdout-$it" })
        val cases = when (caseSet) {
            "development" -> development
            "holdout" -> List(4) { "window-merge-holdout" to "window-holdout-$it" }
            else -> error("Unknown window merge case set")
        }
        val modes = if (caseSet == "holdout") listOf("pad150" to 0L, "merge400" to 400L)
            else listOf("pad150" to 0L, "merge200" to 200L, "merge400" to 400L)
        val rows = JSONArray()
        val evidence = File(context.filesDir, "c2-window-merge-$caseSet-evidence.json")
        for ((suite, name) in cases) {
            val bytes = assets.open("$suite/$name.wav").use { it.readBytes() }
            val sha = MessageDigest.getInstance("SHA-256").digest(bytes)
                .joinToString("") { "%02x".format(it) }
            val audio = bytes.inputStream().use { PcmWav.read(it) }
            val base = IsolatedDiarization.process(context, audio, c2, backend = NemotronBackend.C2)
            val padded = C2BoundaryPadding.apply(base, audio.durationMs)
            for ((mode, gap) in modes) {
                val windows = if (gap == 0L) padded.windows else
                    C2WindowMerge.apply(padded.windows, padded.turns, gap)
                val output = OfflineAsr.transcribe(audio, asr, turns = padded.turns, speechWindows = windows)
                val segments = JSONArray(output.segments.map { segment ->
                    JSONObject().put("start_ms", segment.startMs).put("end_ms", segment.endMs)
                        .put("speaker_id", segment.speakerId ?: JSONObject.NULL).put("text", segment.text)
                })
                rows.put(JSONObject().put("suite", suite).put("case", name).put("mode", mode)
                    .put("audio_sha256", sha).put("audio_ms", audio.durationMs)
                    .put("window_count", windows.size).put("decoded_windows", output.decodedWindows)
                    .put("asr_load_ms", output.loadMs).put("asr_decode_ms", output.decodeMs)
                    .put("segments", segments))
                evidence.writeText(JSONObject().put("runs", rows).toString())
            }
        }
        assertEquals(cases.size * modes.size, rows.length())
    }
}
