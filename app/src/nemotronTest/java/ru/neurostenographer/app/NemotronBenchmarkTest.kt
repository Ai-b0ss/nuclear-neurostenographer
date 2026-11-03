package ru.neurostenographer.app

import android.app.ActivityManager
import android.os.Debug
import android.util.Log
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import ru.neurostenographer.core.*
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import kotlin.concurrent.thread

/** Real C0 and C2 inference on identical recordings through the isolated :diarization process.
 * Evidence holds intervals and measurements. Audio and transcript text stay on the disposable emulator.
 */
class NemotronBenchmarkTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext

    private fun hostInfo() = JSONObject().put("abi", android.os.Build.SUPPORTED_ABIS[0]).put("api", android.os.Build.VERSION.SDK_INT)
        .put("logical_cpus", Runtime.getRuntime().availableProcessors())
        .put("physical_device", !android.os.Build.FINGERPRINT.contains("generic") && !android.os.Build.HARDWARE.contains("ranchu"))

    private fun cluster(turn: SpeakerTurn) = if (turn.speakerId == "Unknown") -1 else turn.speakerId.removePrefix("Speaker ").toInt() - 1

    /** One worker run with PSS of app and worker sampled together, so the peak is a real simultaneous sum. */
    private suspend fun runOnce(audio: PcmAudio, model: File, backend: String): Pair<JSONObject, DiarizationOutput?> {
        val worker = AtomicInteger(0)
        val activity = context.getSystemService(ActivityManager::class.java)
        val sampling = AtomicBoolean(true)
        var peakTotal = 0
        var peakWorker = 0
        var peakApp = 0
        val sampler = thread {
            while (sampling.get()) {
                val app = Debug.MemoryInfo().also(Debug::getMemoryInfo).totalPss
                val pid = worker.get()
                val remote = if (pid != 0) activity.getProcessMemoryInfo(intArrayOf(pid)).firstOrNull()?.totalPss ?: 0 else 0
                peakApp = maxOf(peakApp, app)
                peakWorker = maxOf(peakWorker, remote)
                peakTotal = maxOf(peakTotal, app + remote)
                Thread.sleep(250)
            }
        }
        val started = System.nanoTime()
        val evidence = JSONObject().put("backend", backend).put("audio_ms", audio.durationMs)
        var output: DiarizationOutput? = null
        try {
            output = IsolatedDiarization.process(context, audio, model, backend = backend, onWorkerStarted = worker::set)
            evidence.put("status", "OK").put("load_ms", output.loadMs).put("infer_ms", output.processMs)
                .put("turns", JSONArray(output.turns.map { JSONArray().put(it.startMs).put(it.endMs).put(cluster(it)) }))
                .put("windows", output.windows.size)
        } catch (e: Exception) {
            evidence.put("status", "FAIL").put("error", e.javaClass.simpleName + ": " + e.message)
        }
        evidence.put("wall_ms", (System.nanoTime() - started) / 1_000_000)
        sampling.set(false)
        sampler.join()
        evidence.put("peak_app_pss_kib", peakApp).put("peak_worker_pss_kib", peakWorker).put("peak_total_pss_kib", peakTotal)
        return evidence to output
    }

    /** A damaged C2 model must fail only that request; C0 still works afterwards. This is what a fallback relies on. */
    @Test fun damagedModelFailsAndC0StillWorks(): Unit = runBlocking {
        val assets = instrumentation.context.assets
        val c0 = assets.open("diarization.zip").use { DiarizationModelStore(context).install(it) }
        val c2 = assets.open("nemotron.zip").use { NemotronDiarization.install(context.filesDir, it) }
        val audio = assets.open("nemotron-bench/acted-dmd.wav").use { PcmWav.read(it) }
        val model = File(c2, "model.int8.ir9.onnx")
        val original = model.readBytes()
        model.writeBytes(original.copyOf(1024))
        val (failed, _) = runOnce(audio, c2, NemotronBackend.C2)
        model.writeBytes(original)
        assertEquals("FAIL", failed.getString("status"))
        val (fallback, output) = runOnce(audio, c0, NemotronBackend.C0)
        assertEquals("OK", fallback.getString("status"))
        assertTrue(output!!.turns.isNotEmpty())
    }

    /** Cancelling a long C2 run must end its worker; C0 and C2 both run again afterwards. */
    @Test fun cancelledC2RunReleasesWorker(): Unit = runBlocking {
        val assets = instrumentation.context.assets
        val c0 = assets.open("diarization.zip").use { DiarizationModelStore(context).install(it) }
        val c2 = assets.open("nemotron.zip").use { NemotronDiarization.install(context.filesDir, it) }
        val long = assets.open("nemotron-bench/long-ru_000010.wav").use { PcmWav.read(it) }
        val short = assets.open("nemotron-bench/acted-dmd.wav").use { PcmWav.read(it) }
        val worker = AtomicInteger(0)
        val cancelled = kotlinx.coroutines.withTimeoutOrNull(15_000) {
            IsolatedDiarization.process(context, long, c2, backend = NemotronBackend.C2, onWorkerStarted = worker::set)
        }
        assertEquals("A 20-minute C2 run cannot finish within 15 s here, so it must have been cancelled", null, cancelled)
        assertTrue("Worker never started", worker.get() != 0)
        val (afterC0, _) = runOnce(short, c0, NemotronBackend.C0)
        val (afterC2, _) = runOnce(short, c2, NemotronBackend.C2)
        Log.i("NemotronBench", "cancel worker=${worker.get()} next c0=${afterC0.getString("status")} next c2=${afterC2.getString("status")}")
        assertEquals("OK", afterC0.getString("status"))
        assertEquals("OK", afterC2.getString("status"))
    }

    @Test fun sameRecordingsThroughBothBackends(): Unit = runBlocking {
        val assets = instrumentation.context.assets
        val c0 = assets.open("diarization.zip").use { DiarizationModelStore(context).install(it) }
        val c2 = assets.open("nemotron.zip").use { NemotronDiarization.install(context.filesDir, it) }
        val asr = assets.open("gigaam-v3.zip").use { AsrModelStore(context).install(it) }
        val plan = assets.open("nemotron-bench/plan.tsv").bufferedReader().readLines().filter { it.isNotBlank() }
        val runs = JSONArray()
        val out = File(context.filesDir, "nemotron-evidence.json")
        fun save() = out.writeText(JSONObject().put("device", hostInfo()).put("runs", runs).toString())
        for (line in plan) {
            val (id, repeats, fullPath) = line.split('\t')
            val audio = assets.open("nemotron-bench/$id.wav").use { PcmWav.read(it) }
            for (backend in listOf(NemotronBackend.C0, NemotronBackend.C2)) {
                repeat(repeats.toInt()) { attempt ->
                    val (evidence, output) = runOnce(audio, if (backend == NemotronBackend.C0) c0 else c2, backend)
                    evidence.put("case", id).put("attempt", attempt)
                    if (fullPath == "1" && attempt == 0 && output != null) {
                        val transcript = OfflineAsr.transcribe(audio, asr, turns = output.turns, speechWindows = output.windows)
                        val document = TranscriptDocument(transcript.segments, transcript.audioMs,
                            TranscriptProvenance("emulator", "gigaam", "diarization_boundaries_and_input_windows", backend))
                        val exports = listOf("txt", "srt", "json").map { document.export(it) }
                        evidence.put("transcript", JSONObject().put("segments", transcript.segments.size)
                            .put("attributed_segments", transcript.segments.count { it.speakerId != null })
                            .put("exports_nonblank", exports.all { it.isNotBlank() })
                            .put("json_sha256", MessageDigest.getInstance("SHA-256").digest(exports[2].toByteArray()).joinToString("") { "%02x".format(it) }))
                    }
                    runs.put(evidence)
                    save()
                    Log.i("NemotronBench", "$id $backend ${evidence.getString("status")} ${evidence.optLong("infer_ms")} ms peak ${evidence.getInt("peak_total_pss_kib")} KiB")
                }
            }
        }
        val failures = (0 until runs.length()).map(runs::getJSONObject).filter { it.getString("status") != "OK" }
        assertEquals("Failed runs: $failures", 0, failures.size)
        assertTrue(out.isFile)
    }
}
