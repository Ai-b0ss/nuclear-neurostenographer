package ru.neurostenographer.app

import android.app.ActivityManager
import android.os.Debug
import android.util.Log
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import ru.neurostenographer.core.*
import java.io.File
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import kotlin.concurrent.thread

/** Stress test only: looped public fixtures say nothing about accuracy on a real
 * conversation. Excluded from the regular suite; see tools/run_long_recording.sh.
 */
class LongRecordingTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()

    private fun loopedAudio(seconds: Int): PcmAudio {
        val assets = instrumentation.context.assets
        val parts = listOf("example.wav", "four-speakers.wav").map { name ->
            assets.open(name).use { PcmWav.read(it) }.samples
        }
        val out = FloatArray(seconds * 16000)
        var at = 0
        var index = 0
        while (at < out.size) {
            val part = parts[index++ % parts.size]
            val count = minOf(part.size, out.size - at)
            part.copyInto(out, at, 0, count)
            at += count
        }
        return PcmAudio(out, 16000)
    }

    @Test fun maximumLengthRecordingCompletesFullPipeline(): Unit = runBlocking {
        val context = instrumentation.targetContext
        val asrModel = instrumentation.context.assets.open("gigaam-v3.zip").use { AsrModelStore(context).install(it) }
        val speakerModel = instrumentation.context.assets.open("diarization.zip").use { DiarizationModelStore(context).install(it) }
        val audio = loopedAudio(PcmWav.MAX_SECONDS)
        val workerPid = AtomicInteger(0)
        val activity = context.getSystemService(ActivityManager::class.java)
        var peakAppKib = 0
        var peakWorkerKib = 0
        val sampling = AtomicBoolean(true)
        val sampler = thread {
            while (sampling.get()) {
                val memory = Debug.MemoryInfo().also(Debug::getMemoryInfo)
                peakAppKib = maxOf(peakAppKib, memory.totalPss)
                val pid = workerPid.get()
                if (pid != 0) activity.getProcessMemoryInfo(intArrayOf(pid)).firstOrNull()
                    ?.let { peakWorkerKib = maxOf(peakWorkerKib, it.totalPss) }
                Thread.sleep(2000)
            }
        }
        val started = System.nanoTime()
        val speakers = IsolatedDiarization.process(context, audio, speakerModel, onWorkerStarted = workerPid::set)
        val diarized = System.nanoTime()
        val asr = OfflineAsr.transcribe(audio, asrModel, turns = speakers.turns, speechWindows = speakers.windows)
        val finished = System.nanoTime()
        sampling.set(false)
        sampler.join()
        val evidence = JSONObject().put("scope", "stress_looped_public_fixtures_not_accuracy")
            .put("audio_ms", audio.durationMs).put("device_abi", android.os.Build.SUPPORTED_ABIS[0])
            .put("turns", speakers.turns.size).put("windows", speakers.windows.size)
            .put("segments", asr.segments.size)
            .put("speakers", speakers.turns.filter { it.attributionEligible }.map { it.speakerId }.distinct().size)
            .put("diarization_ms", (diarized - started) / 1_000_000).put("asr_ms", (finished - diarized) / 1_000_000)
            .put("peak_app_pss_kib", peakAppKib).put("peak_worker_pss_kib", peakWorkerKib)
        File(context.filesDir, "long-recording-evidence.json").writeText(evidence.toString(2))
        Log.i("LongRecordingEvidence", evidence.toString())
        assertTrue(speakers.turns.isNotEmpty() && speakers.turns.size <= DiarizationReply.MAX_ITEMS)
        assertTrue(asr.segments.isNotEmpty())
        val document = TranscriptDocument(asr.segments, asr.audioMs, TranscriptProvenance("test", "test", "test", "test"))
        for (format in listOf("txt", "srt", "json")) assertTrue(document.export(format).isNotBlank())
        assertEquals(PcmWav.MAX_SECONDS * 1000L, asr.audioMs)
    }
}
