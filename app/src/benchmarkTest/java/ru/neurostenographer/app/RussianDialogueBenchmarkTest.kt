package ru.neurostenographer.app

import androidx.test.platform.app.InstrumentationRegistry
import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import ru.neurostenographer.core.*
import java.io.File
import java.security.MessageDigest

/** Execution evidence only. Accuracy is scored externally against pinned dataset
 * text after inference. No reference speaker/text is supplied to either engine.
 */
class RussianDialogueBenchmarkTest {
    @Test fun publicActedComposedRussianDialogue(): Unit = runBlocking {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val invocation = requireNotNull(InstrumentationRegistry.getArguments().getString("benchmarkInvocation"))
        require(Regex("[0-9a-f]{32}").matches(invocation))
        val suite = InstrumentationRegistry.getArguments().getString("benchmarkSuite") ?: "development"
        require(suite in setOf("development", "holdout"))
        assertEquals(setOf("aba.wav", "LICENSE.md"), instrumentation.context.assets.list("dialogs")!!.toSet())
        val evidence = File(context.filesDir, "dialogue-benchmark-hypothesis.json")
        evidence.delete()
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val asrStore = AsrModelStore(context)
        val asrModel = instrumentation.context.assets.open("gigaam-v3.zip").use { asrStore.install(it) }
        val speakerStore = DiarizationModelStore(context)
        val speakerModel = instrumentation.context.assets.open("diarization.zip").use { speakerStore.install(it) }
        asrStore.verify(asrModel); speakerStore.verify(speakerModel)
        val bytes = instrumentation.context.assets.open("dialogs/aba.wav").use { it.readBytes() }
        val audio = bytes.inputStream().use { PcmWav.read(it) }
        val before = InferenceEvidence.memorySnapshot()
        fun turnsJson(result: DiarizationOutput): JSONArray = JSONArray().apply {
            result.turns.forEach {
                put(JSONObject().put("start_ms", it.startMs).put("end_ms", it.endMs)
                    .put("speaker_id", if (it.attributionEligible) it.speakerId else JSONObject.NULL)
                    .put("attribution_eligible", it.attributionEligible))
            }
        }
        // The evaluator, not the Android model, knows the externally annotated
        // D-M-D clip boundaries. A sweep must not change the production default
        // or be presented as representative Russian conversation accuracy.
        val outcomes = linkedMapOf<Float, JSONObject>()
        // Legacy 0.9 remains an explicit comparator after changing the default;
        // do not change the user-visible model based only on an authored fixture.
        if (suite == "development") for (threshold in floatArrayOf(0.5f, 0.65f, 0.9f)) {
            val result = IsolatedDiarization.process(context, audio, speakerModel,
                clusteringThreshold = threshold)
            outcomes[threshold] = JSONObject().put("threshold", threshold.toDouble())
                .put("diarization", turnsJson(result))
                .put("process_ms", result.processMs)
        }
        val started = System.nanoTime() // Production timing excludes the experimental sweeps.
        val diarization = IsolatedDiarization.process(context, audio, speakerModel)
        outcomes[OfflineDiarization.THRESHOLD] = JSONObject()
            .put("threshold", OfflineDiarization.THRESHOLD.toDouble())
            .put("diarization", turnsJson(diarization))
            .put("process_ms", diarization.processMs)
        // Holdout runs only the pinned production model: no exploratory sweep.
        val sweep = if (suite == "development") JSONArray().apply {
            for (threshold in floatArrayOf(0.5f, 0.65f, 0.8f, 0.9f))
                put(requireNotNull(outcomes[threshold]))
        } else null
        val asr = OfflineAsr.transcribe(audio, asrModel, turns = diarization.turns, speechWindows = diarization.windows)
        val elapsed = (System.nanoTime() - started) / 1_000_000
        val document = TranscriptDocument(asr.segments, audio.durationMs, TranscriptProvenance(
            "sherpa-onnx-1.12.20/gigaam-v3-ctc-int8", AsrModelStore.REVISION,
            "diarization_boundaries_and_input_windows", DiarizationModelStore.REVISION,
            BuildConfig.SHERPA_RUNTIME_SHA256), listOf(
                if (suite == "holdout") "ACTED_COMPOSED_FOUR_UTTERANCES_DISJOINT_FROM_DEVELOPMENT" else
                    "ACTED_COMPOSED_THREE_UTTERANCES_NOT_NATURAL_DIALOGUE",
                "Chunk boundaries are not word alignment; no independent speech-boundary reference."))
        val hypothesis = JSONObject(document.export("json"))
        val turns = turnsJson(diarization)
        hypothesis.put("audio_sha256", MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it) })
            .put("benchmark_invocation", invocation)
            .put("benchmark_suite", suite)
            .put("diarization", turns)
            .put("production_clustering_threshold", OfflineDiarization.THRESHOLD.toDouble())
            .put("runtime_sha256", BuildConfig.SHERPA_RUNTIME_SHA256)
            .put("sdk_int", Build.VERSION.SDK_INT).put("abis", JSONArray(Build.SUPPORTED_ABIS.toList()))
            .put("device_model", Build.MODEL).put("total_inference_ms", elapsed)
            .put("rtf", elapsed.toDouble() / audio.durationMs)
            .put("timing_scope", "worker bind/load/process/exit plus ASR load/decode; excludes model verification/import; emulator only")
            .put("decoded_windows", asr.decodedWindows)
            .put("memory_before", before).put("memory_after", InferenceEvidence.memorySnapshot())
        if (sweep != null) hypothesis.put("clustering_sweep", sweep)
        evidence.writeText(hypothesis.toString(2), Charsets.UTF_8)
        // These are integrity/execution assertions, never an accuracy threshold.
        assertEquals(audio.durationMs, hypothesis.getLong("audio_duration_ms"))
        assertEquals(BuildConfig.SHERPA_RUNTIME_SHA256, hypothesis.getString("runtime_sha256"))
    }
}
