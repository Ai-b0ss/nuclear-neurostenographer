package ru.neurostenographer.app

import android.Manifest
import android.app.Application
import android.content.Context
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
import ru.neurostenographer.core.Pcm16WavWriter
import ru.neurostenographer.core.PcmWav
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** One opt-in 10-second physical ARM64 flow; always supervised by the host CPU guard.
 * No microphone, permission grants, private audio or product-package instrumentation.
 */
class BatchPowerDeviceTest {
    @Test fun tenSecondPublicAudioCompletesWithDisplayOffAndReleasesCpu() {
        val inst = InstrumentationRegistry.getInstrumentation()
        val target = inst.targetContext
        assumeTrue(target.packageName == "ru.neurostenographer.app.solhigh")
        assumeTrue(InstrumentationRegistry.getArguments().getString("batchPowerQa") == "honor_short")
        check(BuildConfig.ASR_A3 && BuildConfig.NEMOTRON_PROTOTYPE && !BuildConfig.GLOBAL_SPEAKER_BOOK)
        check(Build.MODEL == "DNN-LX9" && Build.VERSION.SDK_INT == 29 &&
            Build.SUPPORTED_ABIS.contains("arm64-v8a"))
        assertEquals(PackageManager.PERMISSION_DENIED, target.checkSelfPermission(Manifest.permission.INTERNET))
        val power = target.getSystemService(PowerManager::class.java)
        val originallyInteractive = power.isInteractive
        val root = File(target.filesDir, "batch-power-qa").apply { mkdirs() }
        val evidence = File(root, "result.json")
        val source = File(target.cacheDir, "batch-power-public-10s.wav")
        val owner = ViewModelStore()
        lateinit var model: TranscriptionViewModel
        var initialized = false
        val record = JSONObject().put("status", "RUNNING").put("scope", "HONOR_ARM64_SHORT_FUNCTIONAL_NOT_ENDURANCE")
            .put("audio_ms", 10_000).put("global_speakerbook", false)
            .put("version", BuildConfig.VERSION_NAME).put("realtime_compiled", BuildConfig.REALTIME)
            .put("sdk", Build.VERSION.SDK_INT).put("model", Build.MODEL)
        evidence.writeText(record.toString(2))
        fun shell(command: String) {
            inst.uiAutomation.executeShellCommand(command).use { fd ->
                android.os.ParcelFileDescriptor.AutoCloseInputStream(fd).use { it.readBytes() }
            }
        }
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
        var failed: Throwable? = null
        try {
            val pcm = inst.context.assets.open("sol-high/aba.wav").use { PcmWav.read(it) }
            check(pcm.samples.size >= 160_000)
            val bytes = ByteBuffer.allocate(320_000).order(ByteOrder.LITTLE_ENDIAN)
            for (i in 0 until 160_000) bytes.putShort((pcm.samples[i].coerceIn(-1f, 1f) * 32767).toInt().toShort())
            bytes.flip()
            Pcm16WavWriter(source, 16000, 1, maxSeconds = 10).use { it.append(bytes); it.finish() }
            inst.runOnMainSync {
                model = TranscriptionViewModel(target.applicationContext as Application)
                initialized = true
                owner.put("batch-power", model)
            }
            await("Bundled model setup failed", 180_000) { !model.state.value.busy }
            assertTrue(model.state.value.modelReady && model.state.value.c2Supported)
            inst.runOnMainSync { model.select(Uri.fromFile(source)) }
            await("Import timed out", 30_000) { !model.state.value.busy }
            check(model.state.value.source != null)
            val begun = SystemClock.elapsedRealtime()
            inst.runOnMainSync { model.transcribe() }
            await("Processing foreground service / CPU lock missing") {
                ProcessingService.active.value && ProcessingService.wakeLockHeld
            }
            // Android 10 permits this user-authorized instrumentation to start the FGS
            // without opening an Activity. No lock-screen dismissal or PIN input.
            shell("input keyevent 223")
            await("Display did not sleep") { !power.isInteractive }
            await("10-second transcription timed out: " + model.state.value.message, 90_000) {
                check(!power.isInteractive) { "Display woke during processing" }
                !model.state.value.busy
            }
            val document = requireNotNull(model.state.value.document) { model.state.value.message }
            assertEquals(10_000L, document.audioMs)
            assertTrue(document.segments.isNotEmpty())
            assertTrue(document.segments.any { Regex("[а-яА-ЯёЁ]{3,}").containsMatchIn(it.text) })
            assertTrue(document.segments.all { it.startMs >= 0 && it.endMs > it.startMs && it.endMs <= 10_000 })
            assertEquals(NemotronBackend.REVISION, document.provenance.speakerSource)
            await("CPU lock or foreground service leaked") {
                !ProcessingService.active.value && !ProcessingService.wakeLockHeld
            }
            record.put("wall_ms", SystemClock.elapsedRealtime() - begun)
                .put("segments", document.segments.size)
                .put("speaker_source", document.provenance.speakerSource)
                .put("screen_off_processing", true).put("processing_wake_lock_released", true)
        } catch (error: Throwable) {
            failed = error
        } finally {
            try {
                inst.runOnMainSync { if (initialized) model.cancel(); owner.clear() }
                await("CPU lock or foreground service leaked at cleanup") {
                    !ProcessingService.active.value && !ProcessingService.wakeLockHeld
                }
                source.delete()
                // Restore only the display power state; never dismiss the keyguard.
                if (originallyInteractive) shell("input keyevent 224")
            } catch (cleanup: Throwable) {
                if (failed == null) failed = cleanup else failed!!.addSuppressed(cleanup)
            }
            record.put("status", if (failed == null) "PASS" else "FAIL")
            failed?.let { record.put("error", it.javaClass.simpleName).put("message", it.message ?: "") }
            evidence.writeText(record.toString(2))
        }
        failed?.let { throw it }
    }
}
