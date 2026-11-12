package ru.neurostenographer.app

import android.Manifest
import android.app.Application
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.net.Uri
import android.os.BatteryManager
import android.os.Build
import android.os.PowerManager
import android.os.SystemClock
import androidx.lifecycle.ViewModelStore
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File

/** One opt-in 20m40s physical ARM64 flow; always supervised by the host CPU guard.
 * No microphone, permission grants, private audio or product-package instrumentation.
 */
class BatchLongPowerDeviceTest {
    @Test fun continuousPublicAudioCompletesWithDisplayOnAndReleasesCpu() {
        val inst = InstrumentationRegistry.getInstrumentation()
        val target = inst.targetContext
        assumeTrue(target.packageName == "ru.neurostenographer.app.solhigh")
        assumeTrue(InstrumentationRegistry.getArguments().getString("batchPowerQa") == "honor_long")
        check(BuildConfig.ASR_A3 && BuildConfig.NEMOTRON_PROTOTYPE && !BuildConfig.GLOBAL_SPEAKER_BOOK)
        check(Build.MODEL == "DNN-LX9" && Build.VERSION.SDK_INT == 29 &&
            Build.SUPPORTED_ABIS.contains("arm64-v8a"))
        assertEquals(PackageManager.PERMISSION_DENIED, target.checkSelfPermission(Manifest.permission.INTERNET))
        val power = target.getSystemService(PowerManager::class.java)
        val root = File(target.filesDir, "batch-power-qa").apply { mkdirs() }
        val evidence = File(root, "long-result.json")
        val source = File(root, "continuous_20m40s.wav")
        val owner = ViewModelStore()
        lateinit var model: TranscriptionViewModel
        var initialized = false
        val record = JSONObject().put("status", "RUNNING").put("scope", "HONOR_ARM64_20M40S_ENDURANCE")
            .put("audio_ms", 1_240_000).put("global_speakerbook", false)
            .put("version", BuildConfig.VERSION_NAME).put("realtime_compiled", BuildConfig.REALTIME)
            .put("batch_asr_threads", InferenceThreads.batchAsrCount())
            .put("sdk", Build.VERSION.SDK_INT).put("model", Build.MODEL)
        evidence.writeText(record.toString(2))
        fun safe() {
            val battery = target.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
                ?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1) ?: -1
            check(battery in 100 until 450 && power.currentThermalStatus < PowerManager.THERMAL_STATUS_SEVERE) {
                "THERMAL_ABORT: battery or Android thermal status"
            }
        }
        fun await(message: String, limit: Long = 5_000, ready: () -> Boolean) {
            val deadline = SystemClock.elapsedRealtime() + limit
            while (!ready() && SystemClock.elapsedRealtime() < deadline) { safe(); SystemClock.sleep(50) }
            check(ready()) { message }
        }
        var screenLease: AutoCloseable? = null
        var failed: Throwable? = null
        try {
            check(source.isFile && source.length() == 39_680_044L) { "Public fixture unavailable: ${source.absolutePath}, exists=${source.exists()}, bytes=${source.length()}" }
            screenLease = PhysicalScreenOnQa.begin()
            record.put("foreground_activity_launched", true)
            inst.runOnMainSync {
                model = TranscriptionViewModel(target.applicationContext as Application)
                initialized = true
                owner.put("batch-power", model)
            }
            await("Bundled model setup failed", 180_000) { !model.state.value.busy }
            assertTrue(model.state.value.modelReady && model.state.value.c2Supported)
            inst.runOnMainSync { model.select(Uri.fromFile(source)) }
            await("Import timed out", 120_000) { !model.state.value.busy }
            check(model.state.value.source != null)
            val begun = SystemClock.elapsedRealtime()
            inst.runOnMainSync { model.transcribe() }
            await("Processing foreground service / CPU lock missing") {
                ProcessingService.active.value && ProcessingService.wakeLockHeld
            }
            // Keep the owned QA window visible; never send display power commands.
            var heartbeatAt = 0L
            await("Long transcription timed out: " + model.state.value.message, 1_140_000) {
                val now = SystemClock.elapsedRealtime()
                if (now - heartbeatAt >= 2_000) {
                    heartbeatAt = now
                    record.put("elapsed_ms", now - begun)
                        .put("processing_stage", model.state.value.stage)
                        .put("progress", model.state.value.progress?.toDouble() ?: JSONObject.NULL)
                    evidence.writeText(record.toString(2))
                }
                check(power.isInteractive) { "Display stopped being interactive during screen-on QA" }
                !model.state.value.busy
            }
            val document = requireNotNull(model.state.value.document) { model.state.value.message }
            assertEquals(1_240_000L, document.audioMs)
            assertTrue(document.segments.isNotEmpty())
            assertTrue(document.segments.any { Regex("[а-яА-ЯёЁ]{3,}").containsMatchIn(it.text) })
            assertTrue(document.segments.all { it.startMs >= 0 && it.endMs > it.startMs && it.endMs <= 1_240_000 })
            assertEquals("chunked_locally_scoped_speakers_no_global_link", document.provenance.speakerSource)
            assertTrue(document.segments.size >= 20)
            val buckets = (0..4).map { index -> document.segments.count { it.startMs / 300_000L == index.toLong() } }
            assertTrue("Every five-minute interval must contribute text", buckets.all { it > 0 })
            assertTrue("No text near the end", document.segments.any { it.endMs > 1_120_000 })
            record.put("segments_by_5min_interval", org.json.JSONArray(buckets))
            await("CPU lock or foreground service leaked") {
                !ProcessingService.active.value && !ProcessingService.wakeLockHeld
            }
            record.put("wall_ms", SystemClock.elapsedRealtime() - begun)
                .put("segments", document.segments.size)
                .put("speaker_source", document.provenance.speakerSource)
                .put("screen_kept_on", true).put("processing_wake_lock_released", true)
        } catch (error: Throwable) {
            failed = error
        } finally {
            try {
                inst.runOnMainSync { if (initialized) model.cancel(); owner.clear() }
                await("CPU lock or foreground service leaked at cleanup") {
                    !ProcessingService.active.value && !ProcessingService.wakeLockHeld
                }
                // The staged source is a public fixture, retained for reproducibility.
            } catch (cleanup: Throwable) {
                if (failed == null) failed = cleanup else failed!!.addSuppressed(cleanup)
            }
            try { screenLease?.close() }
            catch (cleanup: Throwable) {
                if (failed == null) failed = cleanup else failed!!.addSuppressed(cleanup)
            }
            record.put("status", if (failed == null) "PASS" else "FAIL")
            failed?.let { record.put("error", it.javaClass.simpleName).put("message", it.message ?: "") }
            evidence.writeText(record.toString(2))
        }
        failed?.let { throw it }
    }
}
