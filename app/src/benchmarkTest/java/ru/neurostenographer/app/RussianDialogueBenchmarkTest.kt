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
        val started = System.nanoTime()
        val diarization = IsolatedDiarization.process(context, audio, speakerModel)
        val asr = OfflineAsr.transcribe(audio, asrModel, turns = diarization.turns, speechWindows = diarization.windows)
        val elapsed = (System.nanoTime() - started) / 1_000_000
        val document = TranscriptDocument(asr.segments, audio.durationMs, TranscriptProvenance(
            "sherpa-onnx-1.12.20/gigaam-v3-ctc-int8", AsrModelStore.REVISION,
            "diarization_boundaries_and_input_windows", DiarizationModelStore.REVISION,
            BuildConfig.SHERPA_RUNTIME_SHA256), listOf(
                "ACTED_COMPOSED_THREE_UTTERANCES_NOT_NATURAL_DIALOGUE",
                "Chunk boundaries are not word alignment; no independent speech-boundary reference."))
        val hypothesis = JSONObject(document.export("json"))
        val turns = JSONArray()
        diarization.turns.forEach {
            turns.put(JSONObject().put("start_ms", it.startMs).put("end_ms", it.endMs)
                .put("speaker_id", if (it.attributionEligible) it.speakerId else JSONObject.NULL)
                .put("attribution_eligible", it.attributionEligible))
        }
        hypothesis.put("audio_sha256", MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it) })
            .put("diarization", turns).put("runtime_sha256", BuildConfig.SHERPA_RUNTIME_SHA256)
            .put("sdk_int", Build.VERSION.SDK_INT).put("abis", JSONArray(Build.SUPPORTED_ABIS.toList()))
            .put("device_model", Build.MODEL).put("total_inference_ms", elapsed)
            .put("rtf", elapsed.toDouble() / audio.durationMs)
            .put("timing_scope", "worker bind/load/process/exit plus ASR load/decode; excludes model verification/import; emulator only")
            .put("decoded_windows", asr.decodedWindows)
            .put("memory_before", before).put("memory_after", InferenceEvidence.memorySnapshot())
        evidence.writeText(hypothesis.toString(2), Charsets.UTF_8)
        // These are integrity/execution assertions, never an accuracy threshold.
        assertEquals(audio.durationMs, hypothesis.getLong("audio_duration_ms"))
        assertEquals(BuildConfig.SHERPA_RUNTIME_SHA256, hypothesis.getString("runtime_sha256"))
    }
}
