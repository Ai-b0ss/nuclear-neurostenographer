package ru.neurostenographer.app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.PowerManager
import android.os.SystemClock
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import ru.neurostenographer.core.PcmAudio
import ru.neurostenographer.core.PcmWav
import java.io.File
import java.security.MessageDigest

/** Text parity on the same public 10-second probe; no speed/energy population claim. */
class BatchAsrThreadsDeviceTest {
    @Test fun pairedFourAndTwoThreadsPreservePublicProbeText() {
        val inst = InstrumentationRegistry.getInstrumentation()
        val target = inst.targetContext
        assumeTrue(target.packageName == "ru.neurostenographer.app.solhigh")
        assumeTrue(InstrumentationRegistry.getArguments().getString("batchPowerQa") == "honor_asr_threads")
        check(Build.MODEL == "DNN-LX9" && Build.VERSION.SDK_INT == 29)
        check(BuildConfig.ASR_A3 && !BuildConfig.GLOBAL_SPEAKER_BOOK)
        assertEquals(PackageManager.PERMISSION_DENIED, target.checkSelfPermission(Manifest.permission.INTERNET))
        val root = File(target.filesDir, "batch-power-qa").apply { mkdirs() }
        val evidence = File(root, "asr-threads-result.json")
        val record = JSONObject().put("status", "RUNNING")
            .put("scope", "HONOR_ASR_THREADS_PUBLIC_TEXT_PARITY_NOT_ENDURANCE")
            .put("audio_ms", 10_000).put("version", BuildConfig.VERSION_NAME)
            .put("order", JSONArray(listOf(4, 2)))
        evidence.writeText(record.toString(2))
        var screen: AutoCloseable? = null
        var failed: Throwable? = null
        try {
            screen = PhysicalScreenOnQa.begin()
            val original = inst.context.assets.open("sol-high/aba.wav").use { PcmWav.read(it) }
            check(original.samples.size >= 160_000)
            val audio = PcmAudio(original.samples.copyOf(160_000), 16000)
            val store = AsrModelStore(target)
            val model = checkNotNull(store.current())
            store.verify(model)
            val texts = mutableListOf<String>()
            val rows = JSONArray()
            for (threads in listOf(4, 2)) {
                check(target.getSystemService(PowerManager::class.java).isInteractive)
                val began = SystemClock.elapsedRealtime()
                val output = OfflineAsr.transcribe(audio, model, inferenceThreads = threads)
                val wall = SystemClock.elapsedRealtime() - began
                val text = output.segments.joinToString(" ") { it.text.trim() }.trim()
                check(Regex("[а-яА-ЯёЁ]{3,}").containsMatchIn(text))
                check(output.segments.all { it.startMs >= 0 && it.endMs > it.startMs && it.endMs <= 10_000 })
                texts += text
                val digest = MessageDigest.getInstance("SHA-256").digest(text.toByteArray(Charsets.UTF_8))
                    .joinToString("") { "%02x".format(it) }
                rows.put(JSONObject().put("threads", threads).put("wall_ms", wall)
                    .put("segments", output.segments.size).put("text_sha256", digest))
                record.put("rows", rows)
                evidence.writeText(record.toString(2))
            }
            check(texts[0] == texts[1]) { "Thread count changed the public probe transcript" }
            assertEquals(2, InferenceThreads.batchAsrCount())
            assertEquals(InferenceThreads.count(), OfflineAsr.modelConfig(AsrModelSpec.ACTIVE, model).numThreads)
            record.put("text_identical", true).put("batch_asr_threads", InferenceThreads.batchAsrCount())
                .put("realtime_default_threads", InferenceThreads.count()).put("screen_kept_on", true)
                .put("limits", "One ordered 4->2 pair, no statistical speed, accuracy or energy claim")
        } catch (error: Throwable) { failed = error }
        finally {
            try { screen?.close() }
            catch (cleanup: Throwable) { if (failed == null) failed = cleanup else failed!!.addSuppressed(cleanup) }
            record.put("status", if (failed == null) "PASS" else "FAIL")
            failed?.let { record.put("error", it.javaClass.simpleName).put("message", it.message ?: "") }
            evidence.writeText(record.toString(2))
        }
        failed?.let { throw it }
    }
}
