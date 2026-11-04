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

/** Opt-in comparison on independent generator RTTM; no ASR text reference. */
class RubookDerProbeTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext

    @Test fun compareC0C2OnRttm(): Unit = runBlocking {
        val assets = instrumentation.context.assets
        val c0 = assets.open("diarization.zip").use { DiarizationModelStore(context).install(it) }
        val c2 = assets.open("nemotron.zip").use { NemotronDiarization.install(context.filesDir, it) }
        val split = InstrumentationRegistry.getArguments().getString("caseSet") ?: "development"
        val names = when (split) {
            "development" -> listOf("rec_0000", "rec_0055", "rec_0275", "rec_0437")
            "holdout" -> listOf("rec_0001", "rec_0056", "rec_0274", "rec_0438")
            else -> error("Unknown Rubook split")
        }
        val runs = JSONArray()
        val evidence = File(context.filesDir, "rubook-$split-evidence.json")
        for (name in names) {
            val bytes = assets.open("rubook-probe/$name.wav").use { it.readBytes() }
            val hash = MessageDigest.getInstance("SHA-256").digest(bytes)
                .joinToString("") { "%02x".format(it) }
            val audio = bytes.inputStream().use { PcmWav.read(it) }
            for ((backend, model) in listOf(NemotronBackend.C0 to c0, NemotronBackend.C2 to c2)) {
                val output = IsolatedDiarization.process(context, audio, model, backend = backend)
                val turns = JSONArray(output.turns.map { turn ->
                    JSONObject().put("start_ms", turn.startMs).put("end_ms", turn.endMs)
                        .put("speaker_id", turn.speakerId)
                })
                runs.put(JSONObject().put("case", name).put("split", split).put("backend", backend)
                    .put("audio_sha256", hash).put("audio_ms", audio.durationMs)
                    .put("speaker_count", output.turns.map { it.speakerId }.distinct().size)
                    .put("load_ms", output.loadMs).put("infer_ms", output.processMs)
                    .put("turns", turns))
                evidence.writeText(JSONObject().put("runs", runs).toString())
            }
        }
        assertEquals(names.size * 2, runs.length())
    }
}
