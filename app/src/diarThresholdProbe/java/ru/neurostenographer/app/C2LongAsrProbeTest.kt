package ru.neurostenographer.app

import android.app.ActivityManager
import android.os.Debug
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.junit.Test
import ru.neurostenographer.core.PcmWav
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import kotlin.concurrent.thread

/** Opt-in 20-minute natural-call C2 + A0 paired window policy probe on the 4 GiB emulator. */
class C2LongAsrProbeTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext

    private fun samplePss(worker: AtomicInteger, active: AtomicBoolean,
                          peak: IntArray): Thread {
        val manager = context.getSystemService(ActivityManager::class.java)
        return thread {
            while (active.get()) {
                val app = Debug.MemoryInfo().also(Debug::getMemoryInfo).totalPss
                val pid = worker.get()
                val remote = if (pid == 0) 0 else
                    manager.getProcessMemoryInfo(intArrayOf(pid)).firstOrNull()?.totalPss ?: 0
                peak[0] = maxOf(peak[0], app)
                peak[1] = maxOf(peak[1], remote)
                peak[2] = maxOf(peak[2], app + remote)
                Thread.sleep(250)
            }
        }
    }

    @Test fun longRecordingPairedPolicy(): Unit = runBlocking {
        val assets = instrumentation.context.assets
        val c2 = assets.open("nemotron.zip").use { NemotronDiarization.install(context.filesDir, it) }
        val asr = assets.open("gigaam-v3.zip").use { AsrModelStore(context).install(it) }
        val digest = MessageDigest.getInstance("SHA-256")
        assets.open("nemotron-bench/natural-long-ru_000010.wav").use { input ->
            val buffer = ByteArray(1024 * 1024)
            while (true) {
                val size = input.read(buffer)
                if (size < 0) break
                digest.update(buffer, 0, size)
            }
        }
        val hash = digest.digest().joinToString("") { "%02x".format(it) }
        val audio = assets.open("nemotron-bench/natural-long-ru_000010.wav").use { PcmWav.read(it) }
        assertTrue(hash == "e9933e55693151a6f2c5d0f34188348d62053b66a70d9dad0dd25ffd3a408df5")
        assertTrue(audio.durationMs == 1_200_000L)
        val evidence = File(context.filesDir, "c2-natural-long-asr-evidence.json")
        val root = JSONObject().put("audio_sha256", hash).put("audio_ms", audio.durationMs)
            .put("source", "datahiveai/multilingual-conversations-sample:ru_000010:0-1200s")
        val worker = AtomicInteger(0)
        val active = AtomicBoolean(true)
        val peak = IntArray(3)
        val sampler = samplePss(worker, active, peak)
        val diarStarted = System.nanoTime()
        val raw = try {
            IsolatedDiarization.process(context, audio, c2, backend = NemotronBackend.C2,
                onWorkerStarted = worker::set)
        } finally {
            active.set(false)
            sampler.join()
        }
        root.put("diar_wall_ms", (System.nanoTime() - diarStarted) / 1_000_000)
            .put("diar_load_ms", raw.loadMs).put("diar_infer_ms", raw.processMs)
            .put("diar_peak_app_pss_kib", peak[0]).put("diar_peak_worker_pss_kib", peak[1])
            .put("diar_peak_total_pss_kib", peak[2])
        evidence.writeText(root.toString())
        val padded = C2BoundaryPadding.apply(raw, audio.durationMs)
        val merged = C2WindowMerge.apply(padded.windows, padded.turns)
        assertTrue(merged.size <= padded.windows.size)
        for ((mode, windows) in listOf("pad150" to padded.windows, "merge400" to merged)) {
            val appActive = AtomicBoolean(true)
            val appPeak = IntArray(3)
            val appSampler = samplePss(AtomicInteger(0), appActive, appPeak)
            val started = System.nanoTime()
            val output = try {
                OfflineAsr.transcribe(audio, asr, turns = padded.turns, speechWindows = windows)
            } finally {
                appActive.set(false)
                appSampler.join()
            }
            val textDigest = MessageDigest.getInstance("SHA-256").digest(
                output.segments.joinToString("\n") { it.text }.toByteArray(Charsets.UTF_8))
                .joinToString("") { "%02x".format(it) }
            root.put(mode, JSONObject().put("windows", windows.size)
                .put("decoded_windows", output.decodedWindows)
                .put("segments", output.segments.size)
                .put("attributed_segments", output.segments.count { it.speakerId != null })
                .put("text_sha256", textDigest)
                .put("asr_load_ms", output.loadMs).put("asr_decode_ms", output.decodeMs)
                .put("asr_wall_ms", (System.nanoTime() - started) / 1_000_000)
                .put("peak_app_pss_kib", appPeak[0]))
            evidence.writeText(root.toString())
            assertTrue(output.segments.isNotEmpty())
        }
    }
}
