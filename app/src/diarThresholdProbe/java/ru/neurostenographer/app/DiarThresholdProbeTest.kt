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

/** Debug-only fixed threshold sweep on preselected three-speaker recordings. */
class DiarThresholdProbeTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext

    @Test fun compareC0Thresholds(): Unit = runBlocking {
        val assets = instrumentation.context.assets
        val suite = InstrumentationRegistry.getArguments().getString("suite") ?: "asr-holdout"
        require(suite in setOf("asr-holdout", "window-merge-holdout",
            "speaker-refinement-holdout", "nemotron-bench"))
        val c0 = assets.open("diarization.zip").use { DiarizationModelStore(context).install(it) }
        val asr = assets.open("gigaam-v3.zip").use { AsrModelStore(context).install(it) }
        val allCases = InstrumentationRegistry.getArguments().getString("caseList") == "all"
        val cases = (if (suite != "nemotron-bench" || allCases) assets.open("$suite/plan.tsv")
            .bufferedReader().readLines().filter { it.isNotBlank() }.map { it.substringBefore('\t') }
            else listOf("aba", "holdout"))
        val thresholds = listOf(0.5f, 0.65f, 0.8f, 0.9f)
        val rows = JSONArray()
        val evidence = File(context.filesDir, "diar-threshold-evidence.json")
        for (id in cases) {
            val bytes = assets.open("$suite/$id.wav").use { it.readBytes() }
            val sha = MessageDigest.getInstance("SHA-256").digest(bytes)
                .joinToString("") { "%02x".format(it) }
            val audio = bytes.inputStream().use { PcmWav.read(it) }
            for (threshold in thresholds) {
                val diarization = IsolatedDiarization.process(context, audio, c0,
                    clusteringThreshold = threshold, backend = NemotronBackend.C0)
                val asrOutput = OfflineAsr.transcribe(audio, asr, turns = diarization.turns,
                    speechWindows = diarization.windows)
                val turns = JSONArray(diarization.turns.map { turn ->
                    JSONObject().put("start_ms", turn.startMs).put("end_ms", turn.endMs)
                        .put("speaker_id", turn.speakerId)
                })
                val segments = JSONArray(asrOutput.segments.map { segment ->
                    JSONObject().put("start_ms", segment.startMs).put("end_ms", segment.endMs)
                        .put("speaker_id", segment.speakerId ?: JSONObject.NULL)
                        .put("text", segment.text)
                })
                rows.put(JSONObject().put("suite", suite).put("case", id).put("threshold", threshold.toDouble())
                    .put("audio_sha256", sha).put("audio_ms", audio.durationMs)
                    .put("diar_load_ms", diarization.loadMs).put("diar_process_ms", diarization.processMs)
                    .put("asr_load_ms", asrOutput.loadMs).put("asr_decode_ms", asrOutput.decodeMs)
                    .put("speaker_count", diarization.turns.map { it.speakerId }.distinct().size)
                    .put("turns", turns).put("segments", segments))
                evidence.writeText(JSONObject().put("runs", rows).toString())
            }
        }
        assertEquals(cases.size * thresholds.size, rows.length())
    }

    /** Oracle speaker counts from source metadata; evidence for an optional user hint, not an automatic feature. */
    @Test fun compareKnownSpeakerCount(): Unit = runBlocking {
        val assets = instrumentation.context.assets
        val c0 = assets.open("diarization.zip").use { DiarizationModelStore(context).install(it) }
        val asr = assets.open("gigaam-v3.zip").use { AsrModelStore(context).install(it) }
        val cases = listOf(
            Triple("nemotron-bench", "aba", 2), Triple("nemotron-bench", "holdout", 2),
            Triple("nemotron-bench", "ivkond-2clean", 2),
            Triple("nemotron-bench", "ivkond-2overlap", 2),
            Triple("nemotron-bench", "ivkond-3overlap", 3),
            Triple("nemotron-bench", "ivkond-4overlap", 4),
            *Array(4) { Triple("asr-holdout", "acted-holdout-$it", 3) })
        val rows = JSONArray()
        val evidence = File(context.filesDir, "known-speaker-evidence.json")
        for ((suite, id, count) in cases) {
            val bytes = assets.open("$suite/$id.wav").use { it.readBytes() }
            val sha = MessageDigest.getInstance("SHA-256").digest(bytes)
                .joinToString("") { "%02x".format(it) }
            val audio = bytes.inputStream().use { PcmWav.read(it) }
            for (known in listOf(-1, count)) {
                val diarization = IsolatedDiarization.process(context, audio, c0,
                    expectedSpeakers = known, backend = NemotronBackend.C0)
                val asrOutput = OfflineAsr.transcribe(audio, asr, turns = diarization.turns,
                    speechWindows = diarization.windows)
                val segments = JSONArray(asrOutput.segments.map { segment ->
                    JSONObject().put("start_ms", segment.startMs).put("end_ms", segment.endMs)
                        .put("speaker_id", segment.speakerId ?: JSONObject.NULL)
                        .put("text", segment.text)
                })
                rows.put(JSONObject().put("suite", suite).put("case", id)
                    .put("expected_speakers", count).put("requested_speakers", known)
                    .put("predicted_speakers", diarization.turns.map { it.speakerId }.distinct().size)
                    .put("audio_sha256", sha).put("audio_ms", audio.durationMs)
                    .put("diar_process_ms", diarization.processMs)
                    .put("segments", segments))
                evidence.writeText(JSONObject().put("runs", rows).toString())
            }
        }
        assertEquals(cases.size * 2, rows.length())
    }
}
