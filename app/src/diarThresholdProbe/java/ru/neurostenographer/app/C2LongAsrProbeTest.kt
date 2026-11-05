package ru.neurostenographer.app

import android.app.ActivityManager
import android.os.Debug
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.junit.Assert.assertEquals
import org.junit.Test
import ru.neurostenographer.core.PcmWav
import ru.neurostenographer.core.SpeakerTurn
import ru.neurostenographer.core.TranscriptSegment
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import kotlin.concurrent.thread

/** Opt-in 20-minute natural-call C2 + A0/A3 probe on the 4 GiB emulator. */
class C2LongAsrProbeTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext

    private fun unknownReasons(segments: List<TranscriptSegment>, turns: List<SpeakerTurn>): JSONObject {
        val counts = linkedMapOf("no_turn" to 0, "overlap" to 0,
            "ineligible_turn" to 0, "low_coverage_or_margin" to 0,
            "overlap_at_most_100ms" to 0)
        for (segment in segments.filter { it.speakerId == null }) {
            val intersecting = turns.filter { it.startMs < segment.endMs && it.endMs > segment.startMs }
            val reason = when {
                intersecting.isEmpty() -> "no_turn"
                segment.overlappingSpeech -> "overlap"
                intersecting.any { !it.attributionEligible } -> "ineligible_turn"
                else -> "low_coverage_or_margin"
            }
            counts[reason] = counts.getValue(reason) + 1
            if (reason == "overlap" && intersecting.all { it.attributionEligible }) {
                val bySpeaker = intersecting.groupBy { it.speakerId }
                val names = bySpeaker.keys.toList()
                var overlapMs = 0L
                for (i in names.indices) for (j in i + 1 until names.size) {
                    for (a in bySpeaker.getValue(names[i])) for (b in bySpeaker.getValue(names[j])) {
                        overlapMs += (minOf(segment.endMs, a.endMs, b.endMs) -
                            maxOf(segment.startMs, a.startMs, b.startMs)).coerceAtLeast(0)
                    }
                }
                if (overlapMs in 1L..100L) counts["overlap_at_most_100ms"] =
                    counts.getValue("overlap_at_most_100ms") + 1
            }
        }
        return JSONObject(counts as Map<*, *>)
    }

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
        val head = InstrumentationRegistry.getArguments().getString("head") ?: "a0"
        require(head in setOf("a0", "a3"))
        val c2 = assets.open("nemotron.zip").use { NemotronDiarization.install(context.filesDir, it) }
        val asr = if (head == "a0") {
            assets.open("gigaam-v3.zip").use { AsrModelStore(context).install(it) }
        } else {
            File(context.filesDir, "asr-rnnt-v3").also { dir ->
                val hashes = mapOf(
                    "encoder.int8.onnx" to "0ec54e5f130a91c0f228d21795ede10b31c992a1f73e45dcd827e843a71a9b50",
                    "decoder.onnx" to "5d1cfef155d8e07f213bd2f3229b5f6c5c29355c7fa5c1b9eb62cb1925725254",
                    "joiner.onnx" to "fd1d02f45c2ad3d6b67cc149811ad794ab4b020ed49a0a9e2790a8619d1cddd8",
                    "tokens.txt" to "17cc514451bcceac9c280068c71502f8448f99e9fb1456b8d0761651fd0392f2")
                for ((name, expected) in hashes) {
                    val digest = MessageDigest.getInstance("SHA-256")
                    File(dir, name).inputStream().use { input ->
                        val buffer = ByteArray(1024 * 1024)
                        while (true) {
                            val count = input.read(buffer)
                            if (count < 0) break
                            digest.update(buffer, 0, count)
                        }
                    }
                    assertEquals(expected, digest.digest().joinToString("") { "%02x".format(it) })
                }
            }
        }
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
        val evidence = File(context.filesDir, if (head == "a0") "c2-natural-long-asr-evidence.json"
            else "c2-natural-long-a3-evidence.json")
        val root = JSONObject().put("audio_sha256", hash).put("audio_ms", audio.durationMs)
            .put("head", head)
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
        val policies = if (head == "a0") listOf("pad150" to padded.windows,
            "merge400" to merged) else listOf("merge400" to merged)
        for ((mode, windows) in policies) {
            val appActive = AtomicBoolean(true)
            val appPeak = IntArray(3)
            val appSampler = samplePss(AtomicInteger(0), appActive, appPeak)
            val started = System.nanoTime()
            val output = try {
                OfflineAsr.transcribe(audio, asr, turns = padded.turns, speechWindows = windows,
                    threads = if (head == "a3") 2 else InferenceThreads.count())
            } finally {
                appActive.set(false)
                appSampler.join()
            }
            val textDigest = MessageDigest.getInstance("SHA-256").digest(
                output.segments.joinToString("\n") { it.text }.toByteArray(Charsets.UTF_8))
                .joinToString("") { "%02x".format(it) }
            val wordSequence = output.segments.joinToString(" ") { it.text }
                .trim().replace(Regex("\\s+"), " ")
            val wordDigest = MessageDigest.getInstance("SHA-256").digest(
                wordSequence.toByteArray(Charsets.UTF_8))
                .joinToString("") { "%02x".format(it) }
            fun wordCount(items: List<TranscriptSegment>): Int = items.sumOf {
                it.text.trim().split(Regex("\\s+")).count(String::isNotEmpty)
            }
            root.put(mode, JSONObject().put("windows", windows.size)
                .put("decoded_windows", output.decodedWindows)
                .put("segments", output.segments.size)
                .put("attributed_segments", output.segments.count { it.speakerId != null })
                .put("word_count", wordCount(output.segments))
                .put("unattributed_words", wordCount(output.segments.filter { it.speakerId == null }))
                .put("unknown_reasons", unknownReasons(output.segments, padded.turns))
                .put("text_sha256", textDigest)
                .put("word_sequence_sha256", wordDigest)
                .put("asr_load_ms", output.loadMs).put("asr_decode_ms", output.decodeMs)
                .put("asr_wall_ms", (System.nanoTime() - started) / 1_000_000)
                .put("peak_app_pss_kib", appPeak[0]))
            evidence.writeText(root.toString())
            assertTrue(output.segments.isNotEmpty())
        }
    }
}
