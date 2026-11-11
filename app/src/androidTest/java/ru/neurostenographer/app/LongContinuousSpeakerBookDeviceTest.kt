package ru.neurostenographer.app

import android.app.Application
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.net.Uri
import android.os.SystemClock
import android.util.Log
import androidx.lifecycle.ViewModelStore
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File

/** Real >20 min long-file QA on physical Android ARM64. Never uploads recording.
 * Identity accuracy is NOT inferred from this endurance/functional test.
 */
class LongContinuousSpeakerBookDeviceTest {
    @Test fun continuousTwentyMinuteRecordingCompletesWithoutLosingTimeOrText() {
        val inst = InstrumentationRegistry.getInstrumentation()
        val target = inst.targetContext
        assumeTrue(BuildConfig.GLOBAL_SPEAKER_BOOK)
        val source = File(requireNotNull(target.getExternalFilesDir("qa")), "continuous_20m40s.wav")
        assertTrue("ADB must stage the controlled local recording", source.isFile)
        val evidence = File(target.filesDir, "speakerbook-long-20min-evidence.json")
        val store = ViewModelStore()
        lateinit var model: TranscriptionViewModel
        var modelInitialized = false
        var stage = "startup"
        val begun = SystemClock.elapsedRealtime()
        // Overwrite any stale success evidence BEFORE processing starts.
        val runId = SystemClock.elapsedRealtimeNanos().toString()
        evidence.writeText(JSONObject()
            .put("run_id", runId).put("status", "RUNNING")
            .put("scope", "long_20min_device_qa").toString(2))
        // The previous 20m test was aborted when the HONOR battery sensor
        // reached 47 C. For this *test only*, never start hot or continue
        // above a conservative 42 C cutoff (sensor reads tenths of a degree).
        val highestSafeBatteryTenths = 420
        var peakBatteryTenths = 0
        fun verifyCoolBattery() {
            val reading = target.registerReceiver(
                null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
                ?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1) ?: -1
            assertTrue("Battery temperature unavailable; fail closed", reading in 100..650)
            if (reading > peakBatteryTenths) peakBatteryTenths = reading
            if (reading >= highestSafeBatteryTenths) {
                inst.runOnMainSync { if (modelInitialized) model.cancel() }
                throw AssertionError("THERMAL_ABORT: battery reached " +
                    (reading / 10.0) + " C; test cutoff 42.0 C")
            }
        }
        fun awaitIdle(maxMillis: Long) {
            val deadline = SystemClock.elapsedRealtime() + maxMillis
            verifyCoolBattery()
            while (model.state.value.busy && SystemClock.elapsedRealtime() < deadline) {
                SystemClock.sleep(350)
                verifyCoolBattery()
            }
            assertFalse("Timed out in " + stage + ": " + model.state.value.message, model.state.value.busy)
            verifyCoolBattery()
        }

        try {
            verifyCoolBattery()
            inst.runOnMainSync {
                model = TranscriptionViewModel(target.applicationContext as Application)
                modelInitialized = true
                store.put("speaker-book-long-real-qa", model)
            }
            assertTrue("ASR not provisioned", model.state.value.modelReady)
            stage = "import_20min"
            inst.runOnMainSync { model.select(Uri.fromFile(source)) }
            awaitIdle(180_000L)
            val duration = model.state.value.sourceDurationMs ?: 0L
            assertTrue("This must exercise real >20 min logic, not 5 min QA shortcut", duration > 20 * 60 * 1000L)
            assertTrue("Import was rejected: " + model.state.value.message, model.state.value.source != null)
            stage = "recognize_20min"
            val recognitionStart = SystemClock.elapsedRealtime()
            inst.runOnMainSync { model.transcribe() }
            awaitIdle(900_000L)
            val recognitionMillis = SystemClock.elapsedRealtime() - recognitionStart
            val doc = requireNotNull(model.state.value.document) {
                "Transcript not produced: " + model.state.value.message
            }
            val segments = doc.segments
            val ids = segments.mapNotNull { it.speakerId }.toSet()
            val warning = doc.warnings.joinToString(" ")
            val profileBlocks = Regex("профили получены для ([0-9]+) блоков")
                .find(warning)?.groupValues?.get(1)?.toIntOrNull() ?: 0
            val buckets = (0..((duration / 300_000L).toInt())).map { index ->
                segments.count { it.startMs / 300_000L == index.toLong() }
            }
            val result = JSONObject()
                .put("run_id", runId)
                .put("scope", "20min40s_continuous_test_audio_no_ground_truth")
                .put("duration_ms", duration)
                .put("wall_ms", recognitionMillis)
                .put("rtf", recognitionMillis.toDouble() / duration)
                .put("max_battery_temperature_c", peakBatteryTenths / 10.0)
                .put("segments", segments.size)
                .put("speaker_id_count", ids.size)
                .put("unknown_segments", segments.count { it.speakerId == null })
                .put("profiled_blocks", profileBlocks)
                .put("speaker_source", doc.provenance.speakerSource)
                .put("segments_by_5min_interval", JSONArray(buckets))
                .put("warning", warning)
            assertEquals("Long-file duration must be preserved", duration, doc.audioMs)
            assertTrue("No ASR result for real continuous recording", segments.size >= 20)
            assertTrue("All transcript segments must be within audio",
                segments.all { it.startMs >= 0 && it.endMs > it.startMs && it.endMs <= duration })
            assertTrue("Transcript must be ordered", segments.zipWithNext().all { (a, b) -> a.startMs <= b.startMs })
            assertTrue("No segments at the beginning", segments.any { it.startMs < 120_000L })
            assertTrue("No segments near end", segments.any { it.endMs > duration - 120_000L })
            assertTrue("All four complete 5 minute windows must contribute text",
                buckets.take(4).all { it > 0 })
            assertTrue("No speaker identification at all", ids.isNotEmpty())
            assertTrue("No C2 profiling at all", profileBlocks > 0)
            assertEquals("Long recording must use specialized voice embeddings",
                "chunked_titanet_small_voice_embeddings_qa", doc.provenance.speakerSource)
            // Success only AFTER every postcondition has been established.
            result.put("status", "PASS")
            evidence.writeText(result.toString(2))
            Log.i("SpeakerBookLongDeviceQA", result.toString())
        } catch (e: Throwable) {
            // A failed assertion or cancellation MUST REPLACE stale success
            // evidence from an earlier run. Always persist a terminal state.
            val thermal = e.message?.startsWith("THERMAL_ABORT") == true
            evidence.writeText(JSONObject()
                .put("run_id", runId)
                .put("status", if (thermal) "THERMAL_ABORT" else "FAIL")
                .put("scope", "long_20min_device_qa_error")
                .put("stage", stage).put("error", e.javaClass.simpleName)
                .put("message", e.message ?: "")
                .put("peak_battery_temperature_c", peakBatteryTenths / 10.0)
                .put("elapsed_ms", SystemClock.elapsedRealtime() - begun).toString(2))
            throw e
        } finally {
            if (modelInitialized) {
                inst.runOnMainSync { model.cancel() }
                // Cancellation request alone does not prove that native
                // computation stopped; wait briefly and log that uncertainty.
                val deadline = SystemClock.elapsedRealtime() + 5_000L
                while (model.state.value.busy && SystemClock.elapsedRealtime() < deadline)
                    SystemClock.sleep(200)
                if (model.state.value.busy) {
                    Log.e("SpeakerBookLongDeviceQA",
                        "Native worker cancellation unacknowledged; host-side ADB watchdog required")
                }
            }
            inst.runOnMainSync { store.clear() }
        }
    }
}
