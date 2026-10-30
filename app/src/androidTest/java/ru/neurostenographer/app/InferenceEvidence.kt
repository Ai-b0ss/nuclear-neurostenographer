package ru.neurostenographer.app

import android.os.Build
import android.os.Debug
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import ru.neurostenographer.core.PcmAudio
import ru.neurostenographer.core.TranscriptExport
import java.io.File
import java.security.MessageDigest

/** Public fixtures only. Persist independently of logcat and later failing assertions. */
object InferenceEvidence {
    fun memorySnapshot(): JSONObject {
        val memory = Debug.MemoryInfo()
        Debug.getMemoryInfo(memory)
        return JSONObject().put("process_pss_kib", memory.totalPss)
            .put("java_used_bytes", Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory())
            .put("scope", "current instrumentation/app process snapshot; NOT peak, excludes diarization worker")
    }

    private fun base(audio: PcmAudio, fixture: String): JSONObject {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val digest = MessageDigest.getInstance("SHA-256")
        instrumentation.context.assets.open(fixture).use { stream ->
            val buffer = ByteArray(65536)
            while (true) {
                val n = stream.read(buffer)
                if (n < 0) break
                digest.update(buffer, 0, n)
            }
        }
        return JSONObject().put("schema_version", 1).put("platform", "Android instrumentation")
            .put("sdk_int", Build.VERSION.SDK_INT).put("abis", JSONArray(Build.SUPPORTED_ABIS.toList()))
            .put("device_model", Build.MODEL).put("audio_duration_ms", audio.durationMs)
            .put("audio_sha256", digest.digest().joinToString("") { "%02x".format(it) })
            .put("fixture", fixture).put("reference_status", "No independent full text or speech-boundary annotation; WER/DER/cpWER NOT_SCORED")
    }

    fun asr(audio: PcmAudio, output: AsrOutput, run: Int, before: JSONObject) {
        val data = base(audio, "example.wav")
        val document = JSONObject(TranscriptExport.json(output.segments))
        data.put("segments", document.getJSONArray("segments"))
            .put("model_revision", AsrModelStore.REVISION).put("run", run)
            .put("load_ms", output.loadMs).put("decode_ms", output.decodeMs)
            .put("load_plus_decode_rtf", (output.loadMs + output.decodeMs).toDouble() / audio.durationMs)
            .put("timing_scope", "fresh recognizer per run; excludes model hash verification, PCM import, diarization; not cold process startup")
            .put("memory_before", before).put("memory_after", memorySnapshot())
        write("asr-$run.json", data)
    }

    fun diarization(audio: PcmAudio, output: DiarizationOutput, run: Int) {
        val turns = JSONArray()
        output.turns.forEach {
            turns.put(JSONObject().put("start_ms", it.startMs).put("end_ms", it.endMs)
                .put("speaker_id", if (it.attributionEligible) it.speakerId else JSONObject.NULL)
                .put("attribution_eligible", it.attributionEligible))
        }
        write("diarization-$run.json", base(audio, "four-speakers.wav")
            .put("segments", JSONArray()).put("diarization", turns)
            .put("model_revision", DiarizationModelStore.REVISION)
            .put("load_ms", output.loadMs).put("process_ms", output.processMs)
            .put("memory_after", memorySnapshot()))
    }

    private fun write(name: String, data: JSONObject) {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val root = File(context.filesDir, "inference-evidence").apply { mkdirs() }
        File(root, name).writeText(data.toString(2), Charsets.UTF_8)
    }
}
