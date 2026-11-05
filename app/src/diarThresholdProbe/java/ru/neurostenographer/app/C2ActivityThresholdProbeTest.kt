package ru.neurostenographer.app

import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import ru.neurostenographer.core.PcmWav
import java.io.File
import java.security.MessageDigest

/** Debug-only native logit threshold sweep; does not change production C2. */
class C2ActivityThresholdProbeTest {
    @Test fun compareActivityThresholds() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val assets = instrumentation.context.assets
        val model = assets.open("nemotron.zip").use { NemotronDiarization.install(context.filesDir, it) }
        val cases = listOf(
            "ami-meeting" to "ES2004a-360-600",
            "ami-meeting" to "IS1009a-360-600",
            "rubook-probe" to "rec_0001",
            "rubook-probe" to "rec_0275"
        )
        val runs = JSONArray()
        val evidence = File(context.filesDir, "c2-activity-threshold-evidence.json")
        for ((suite, name) in cases) {
            val bytes = assets.open("$suite/$name.wav").use { it.readBytes() }
            val hash = MessageDigest.getInstance("SHA-256").digest(bytes)
                .joinToString("") { "%02x".format(it) }
            val audio = bytes.inputStream().use { PcmWav.read(it) }
            for (threshold in listOf(0f, -0.25f, -0.5f)) {
                val output = NemotronDiarization.process(audio, model,
                    activityThreshold = threshold)
                val turns = JSONArray(output.turns.map { t ->
                    JSONObject().put("start_ms", t.startMs).put("end_ms", t.endMs)
                        .put("speaker_id", t.speakerId)
                })
                runs.put(JSONObject().put("suite", suite).put("case", name)
                    .put("activity_threshold", threshold.toDouble())
                    .put("audio_sha256", hash).put("audio_ms", audio.durationMs)
                    .put("load_ms", output.loadMs).put("infer_ms", output.processMs)
                    .put("turns", turns))
                evidence.writeText(JSONObject().put("runs", runs).toString())
            }
        }
        assertEquals(cases.size * 3, runs.length())
    }
}
