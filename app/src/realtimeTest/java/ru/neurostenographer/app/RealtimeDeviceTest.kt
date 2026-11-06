package ru.neurostenographer.app

import android.Manifest
import android.content.Intent
import android.os.SystemClock
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import ru.neurostenographer.core.*
import java.io.File
import java.security.MessageDigest
import java.util.UUID

/** Physical ARM64 evidence is retrieved only from this separate applicationId. */
class RealtimeDeviceTest {
    private val ins = InstrumentationRegistry.getInstrumentation()
    private val context get() = ins.targetContext
    private val args get() = InstrumentationRegistry.getArguments()
    private fun sha(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { source -> val b = ByteArray(65536); while (true) { val n = source.read(b); if (n < 0) break; digest.update(b, 0, n) } }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
    private fun directory(name: String) = File(context.filesDir, "realtime/test-$name-${UUID.randomUUID()}").apply { mkdirs() }
    private fun holdForeground() {
        context.startForegroundService(Intent(context, RealtimeService::class.java).putExtra("benchmarkHold", true))
        val deadline = SystemClock.elapsedRealtime() + 10000
        while (!RealtimeService.foreground && SystemClock.elapsedRealtime() < deadline) SystemClock.sleep(50)
        check(RealtimeService.foreground) { "Synthetic test requires own foreground service" }
    }
    private fun releaseForeground() { context.startService(Intent(context, RealtimeService::class.java).setAction("STOP")) }

    @Test fun importedRussianStreaming() {
        // A visible own Activity avoids OEM freezing an invisible instrumentation-only process.
        // It does not start microphone capture or install models concurrently.
        val activity = ins.startActivitySync(Intent(context, RealtimeActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        holdForeground()
        val clip = args.getString("clip") ?: "syn3-clean"
        require(clip in listOf("syn3-clean", "syn3-brown", "syn4-noise", "silence", "overlap", "aba", "single",
            // Public synthetic audiobook RTTM evaluation; clips are pushed externally, never bundled.
            "rec_0150", "rec_0300", "rec_0437",
            // Public human volunteers reading scripted meetings, anonymous speaker labels only.
            "veche-2-one-to-one", "veche-3-auth-incident"))
        val input = context.getExternalFilesDirs(null).filterNotNull().map { File(it, "realtime-fixtures/$clip.wav") }.first { it.isFile }
        val audio = input.inputStream().use { PcmWav.read(it) }
        val paced = args.getString("paced", "true") == "true"
        val fallback = args.getString("fallback", "false") == "true"
        val pause = args.getString("pause", "500")!!.toInt()
        val root = directory(clip)
        File(context.filesDir, "realtime-last-synthetic.txt").writeText(root.name)
        val journal = RealtimeJournal(File(root, "capture.wav"))
        val sourceHash = sha(input)
        val session = RealtimeSession(context, journal, RealtimeOptions(pause, fallback, adaptive = false, paced = paced,
            invocation = args.getString("invocation"),
            consensusExperimental = args.getString("consensus", "false") == "true",
            c2Chunk72AfterThreeExperimental = args.getString("chunk72", "false") == "true"))
        var maxFeedLatenessMs = 0L
        var producerElapsedMs = 0L
        val producer = Thread {
            try {
                var at = 0
                val beginning = System.nanoTime()
                while (at < audio.samples.size) {
                    val count = minOf(512, audio.samples.size - at)
                    val frame = ShortArray(count) { (audio.samples[at + it] * 32768).toInt().toShort() }
                    journal.append(frame, count); at += count
                    maxFeedLatenessMs = maxOf(maxFeedLatenessMs,
                        (System.nanoTime() - beginning - at * 1_000_000_000L / 16000) / 1_000_000)
                    if (paced) {
                        val remaining = beginning + at * 1_000_000_000L / 16000 - System.nanoTime()
                        if (remaining > 0) Thread.sleep(remaining / 1_000_000, (remaining % 1_000_000).toInt())
                    }
                }
                producerElapsedMs = (System.nanoTime() - beginning) / 1_000_000
            } catch (e: Throwable) { journal.failure = e.toString() }
            finally { journal.finish() }
        }
        try {
            producer.start(); session.start()
            producer.join(180000); assertFalse("Producer stuck", producer.isAlive)
            assertTrue("Inference timeout", session.join(240000))
            assertEquals("Native/session failure: ${session.failure}", "COMPLETE", session.state)
            assertNull(journal.failure)
            assertEquals(audio.samples.size.toLong(), journal.samples)
            val saved = journal.file.inputStream().use { PcmWav.read(it) }
            assertArrayEquals("PCM persisted without gaps/duplication", audio.samples, saved.samples, 0f)
            assertNotNull(session.document)
            // Crash-consistent multi-file export: one revision/manifest and valid hashes.
            val published = requireNotNull(TranscriptSnapshotStore(root).current())
            assertEquals("FINAL", published.state)
            assertEquals(journal.samples / 16, published.audioMs)
            assertTrue(File(root, "transcript-current.json").isFile)
            for (format in listOf("json", "txt", "srt")) {
                val canonical = File(published.json.parentFile, "transcript.$format")
                val legacy = File(root, "transcript.$format")
                assertEquals("Canonical/legacy mismatch: $format", sha(canonical), sha(legacy))
            }
            if (clip == "silence") assertTrue(session.document!!.segments.isEmpty())
            else assertTrue("Real ASR produced no text", session.document!!.segments.isNotEmpty())
            val report = JSONObject(File(root, "metrics.json").readText()).put("test_status", "PASS")
                .put("invocation", args.getString("invocation"))
                .put("producer_elapsed_ms", producerElapsedMs).put("max_feed_lateness_ms", maxFeedLatenessMs)
                .put("pacing_valid", !paced || maxFeedLatenessMs < 250)
                .put("clip", clip).put("fixture_sha256", sourceHash).put("captured_wav_sha256", sha(journal.file))
                .put("pcm_exact", true).put("input_samples", audio.samples.size)
            File(root, "metrics.json").writeText(report.toString(2))
            // Only this synthetic-fixture directory is eligible for export by the collector.
            File(context.filesDir, "realtime-last-synthetic.txt").writeText(root.name)
        } finally {
            session.cancel(); producer.join(10000); session.join(30000)
            if (!producer.isAlive && !session.isRunning) journal.close()
            releaseForeground()
            ins.runOnMainSync { activity.finish() }
        }
    }

    @Test fun transcriptSnapshotCrashRecovery() {
        // Uses only internally generated test text; no microphone or external audio.
        val stages = listOf("after-json", "after-txt", "after-srt", "after-snapshot",
            "after-directory", "after-pointer", "after-compat-json", "after-compat-txt")
        val cases = JSONArray()
        for (stage in stages) {
            val own = directory("snapshot-crash")
            val first = TranscriptSnapshotStore(own).publish(
                """{"text":"old"}""", "old", "old", 1000, false)
            assertEquals(1L, first.number)
            val aborted = TranscriptSnapshotStore(own) { at ->
                if (at == stage) throw IllegalStateException("Simulated process death")
            }
            assertTrue("Crash injection was ignored: $stage",
                runCatching { aborted.publish("""{"text":"new"}""", "new", "new", 2000, true) }.isFailure)
            val reopened = TranscriptSnapshotStore(own)
            val latest = requireNotNull(reopened.current())
            val pointerCommitted = stage == "after-pointer" || stage.startsWith("after-compat-")
            assertEquals("Wrong authoritative snapshot after $stage",
                if (pointerCommitted) 2L else 1L, latest.number)
            assertEquals(if (pointerCommitted) "FINAL" else "PROVISIONAL", latest.state)
            assertEquals(if (pointerCommitted) "new" else "old", latest.txt.readText())
            assertEquals(if (pointerCommitted) "new" else "old", latest.srt.readText())
            val fresh = reopened.publish("""{"text":"restarted"}""", "restart", "restart", 3000, true)
            assertTrue("Pending revision caused collision", fresh.number >= 3L)
            assertEquals(fresh.number, reopened.current()!!.number)
            cases.put(JSONObject().put("stage", stage).put("pass", true)
                .put("original_revision", latest.number)
                .put("restarted_revision", fresh.number))
        }
        val performance = directory("snapshot-retention")
        val store = TranscriptSnapshotStore(performance)
        repeat(128) { index ->
            store.publish("""{"index":$index}""", "таймкод $index", "таймкод $index", 1000L+index, false)
        }
        assertEquals(128L, store.current()?.number)
        assertEquals(3, File(performance, "transcript-versions").listFiles()!!
            .count { it.isDirectory && it.name.startsWith("v") })
        File(context.filesDir, "realtime-snapshot-recovery.json").writeText(JSONObject()
            .put("status", "PASS")
            .put("scope", "PHYSICAL_ANDROID_ATOMIC_POINTER_AND_CRASH_INJECTION_NO_ASR")
            .put("crash_cases", cases)
            .put("retention_revisions", 3)
            .put("stress_publications", 128)
            .put("last_revision", store.current()!!.number).toString(2))
    }

    @Test fun hourJournalBounded() {
        val root = directory("hour-journal")
        val before = android.os.Debug.getPss()
        val started = System.nanoTime()
        val journal = RealtimeJournal(File(root, "capture.wav"))
        try {
            val frame = ShortArray(512) { (it - 256).toShort() }
            val total = 3600L * 16000
            var at = 0L
            while (at < total) {
                val count = minOf(512L, total - at).toInt()
                journal.append(frame, count); at += count
            }
            journal.finish()
            assertEquals(total, journal.samples)
            assertEquals(44 + total * 2, journal.file.length())
            for (offset in listOf(0L, 1800L * 16000, total - 512)) {
                val read = journal.read(offset, 512)
                for (i in read.indices) assertEquals(frame[i] / 32768f, read[i], 0f)
            }
            File(context.filesDir, "realtime-hour-journal.json").writeText(JSONObject()
                .put("status", "PASS").put("scope", "PHYSICAL_ACCELERATED_ONE_HOUR_PCM_JOURNAL_NO_MODEL_NO_PACING")
                .put("samples", total).put("wav_bytes", journal.file.length()).put("pss_before_kb", before)
                .put("pss_after_kb", android.os.Debug.getPss()).put("elapsed_ms", (System.nanoTime() - started) / 1000000)
                .put("disk_reads", journal.diskReads).toString(2))
        } finally { journal.close() }
    }

    @Test fun c2OfflineParity() {
        val activity = ins.startActivitySync(Intent(context, RealtimeActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        holdForeground()
        try {
        val input = context.getExternalFilesDirs(null).filterNotNull().map { File(it, "realtime-fixtures/syn3-clean.wav") }.first { it.isFile }
        val audio = input.inputStream().use { PcmWav.read(it) }
        val raw = RealtimeNative(context, NemotronChunkConfig.OFFLINE).use { native ->
            while (native.diarizer.canStep(audio.samples.size.toLong(), true)) native.diarizer.step(audio.samples.size.toLong(), true) { start, n ->
                audio.samples.copyOfRange(start.toInt(), start.toInt() + n)
            }
            native.diarizer.snapshot(audio.samples.size.toLong())
        }
        val expected = NemotronDiarization.process(audio, requireNotNull(NemotronBackend.current(context.filesDir)))
        val actual = DiarizationTimeline.canonicalize(raw, audio.durationMs)
        assertEquals("Parameterizing C2 must preserve offline intervals", expected.turns, actual)
        File(context.filesDir, "realtime-parity.json").writeText(JSONObject().put("status", "PASS")
            .put("scope", "PHYSICAL_C2_ORIGINAL_OFFLINE_VS_INCREMENTAL_OFFLINE_CONFIG")
            .put("fixture_sha256", sha(input)).put("turns", actual.size).put("exact_turn_parity", true).toString(2))
        } finally { releaseForeground(); ins.runOnMainSync { activity.finish() } }
    }

    @Test fun damagedC2KeepsAsrAlive() {
        val activity = ins.startActivitySync(Intent(context, RealtimeActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        holdForeground()
        val broken = File(context.cacheDir, "realtime-broken-c2-${UUID.randomUUID()}").apply { mkdirs() }
        try {
            val input = context.getExternalFilesDirs(null).filterNotNull().map { File(it, "realtime-fixtures/syn3-clean.wav") }.first { it.isFile }
            val audio = input.inputStream().use { PcmWav.read(it) }
            RealtimeNative(context, NemotronChunkConfig.FAST, c2Override = broken).use { native ->
                assertFalse(native.hasDiarizer); assertNotNull(native.diarizationFailure)
                val decoded = native.decode(audio.samples.copyOfRange(0, 48000), SampleSpan(0, 48000, 48000))
                assertTrue("ASR must survive damaged C2", decoded.first.isNotEmpty() || decoded.second != null)
            }
            File(context.filesDir, "realtime-c2-fallback.json").writeText(JSONObject().put("status", "PASS")
                .put("scope", "PHYSICAL_MISSING_C2_PIN_REJECTED_REAL_A3_STILL_DECODES_UNKNOWN_SPEAKERS").toString(2))
        } finally { broken.delete(); releaseForeground(); ins.runOnMainSync { activity.finish() } }
    }

    @Test fun microphoneCaptureOnlyAndRestart() {
        assertEquals(android.content.pm.PackageManager.PERMISSION_GRANTED, context.checkSelfPermission(Manifest.permission.RECORD_AUDIO))
        val results = JSONArray()
        repeat(2) {
            val dir = directory("mic-private")
            val journal = RealtimeJournal(File(dir, "capture.wav"))
            val capture = RealtimeCapture(context, journal, seconds = 8)
            val began = SystemClock.elapsedRealtime()
            try {
                capture.start(); SystemClock.sleep(2500); capture.requestStop()
                assertTrue(capture.join(5000)); assertNull(journal.failure)
                assertTrue(journal.samples in 16000L..80000L)
                val saved = journal.file.inputStream().use { PcmWav.read(it) }
                assertEquals(journal.samples, saved.samples.size.toLong())
                results.put(JSONObject().put("samples", journal.samples).put("wall_ms", SystemClock.elapsedRealtime() - began)
                    .put("audio_ms", saved.durationMs).put("max_read_gap_ms", capture.maxReadGapMs)
                    .put("hardware_frame_position", capture.hardwareFramePosition).put("hardware_timestamp_samples", capture.timestampSamples))
            } finally {
                capture.requestStop(); capture.join(5000)
                if (!capture.isRunning) journal.close()
                // Private mic audio stays on the phone; never transcribed or pulled by collector.
            }
        }
        File(context.filesDir, "realtime-microphone.json").writeText(JSONObject().put("status", "PASS")
            .put("scope", "CAPTURE_ONLY_NO_SPEECH_INFERENCE_NO_AUDIO_EXPORT").put("runs", results).toString(2))
    }

    @Test fun cancellationRecoveryAndRestart() {
        val root = directory("recovery")
        val journal = RealtimeJournal(File(root, "capture.wav"))
        journal.append(ShortArray(512) { 19 }, 512)
        repeat(5) { journal.append(ShortArray(512) { 27 }, 512) }
        // Test a torn header while persisted PCM remains intact. Recovery never invents samples.
        val before = journal.samples
        assertEquals(before, RealtimeJournal.recover(journal.file))
        journal.finish(); journal.close()
        val read = journal.file.inputStream().use { PcmWav.read(it) }
        assertEquals(before, read.samples.size.toLong())
        val nextRoot = directory("cancel")
        val next = RealtimeJournal(File(nextRoot, "capture.wav"))
        repeat(32) { next.append(ShortArray(512), 512) }; next.finish()
        val session = RealtimeSession(context, next)
        session.cancel(); session.start()
        assertTrue(session.join(90000)); assertEquals("CANCELLED", session.state)
        assertEquals(32812L, next.file.length()); next.close()
        File(context.filesDir, "realtime-recovery.json").writeText(JSONObject().put("status", "PASS")
            .put("scope", "AUTHORED_TORN_HEADER_RECOVERY_AND_CANCEL_BEFORE_INFERENCE").put("samples_recovered", before)
            .put("restart_microphone_test", "separate microphoneCaptureOnlyAndRestart").toString(2))
    }

    @Test fun recoveryKeepsCompletedAndShortInterruptedAudio() {
        // Isolate recovery from unrelated historical user recordings.
        val sandbox = File(context.cacheDir, "recovery-scope-${UUID.randomUUID()}")
        val base = File(sandbox, "realtime").apply { mkdirs() }
        try {
            val doneDir = File(base, "completed").apply { mkdirs() }
            val done = RealtimeJournal(File(doneDir, "capture.wav"))
            repeat(4) { done.append(ShortArray(512) { 123 }, 512) }
            done.finish(); done.close()
            val originalSha = sha(done.file)
            assertTrue(File(doneDir, "capture-finalized.txt").exists())

            val tornDir = File(base, "interrupted").apply { mkdirs() }
            val torn = RealtimeJournal(File(tornDir, "capture.wav"))
            torn.append(shortArrayOf(1234), 1)
            torn.close() // Crash simulation: only raw PCM, zeroed WAV header.
            java.io.RandomAccessFile(torn.file, "rw").use {
                it.seek(it.length()); it.write(0xAB) // Torn half-sample must be discarded.
            }
            assertEquals(47L, torn.file.length())

            val emptyDir = File(base, "empty").apply { mkdirs() }
            val empty = RealtimeJournal(File(emptyDir, "capture.wav"))
            empty.close()

            RealtimeService.recover(sandbox)
            assertEquals("Do not mutate finalized audio", originalSha, sha(done.file))
            assertFalse("Completed recording must not be labeled as recovered",
                File(doneDir, "recovered.txt").exists())

            assertEquals(46L, torn.file.length())
            java.io.RandomAccessFile(torn.file, "r").use { wav ->
                assertEquals("RIFF", ByteArray(4).also { wav.readFully(it) }.toString(Charsets.US_ASCII))
                assertEquals(38, Integer.reverseBytes(wav.readInt()))
                wav.seek(40)
                assertEquals(2, Integer.reverseBytes(wav.readInt()))
                assertEquals(0xD2, wav.readUnsignedByte())
                assertEquals(0x04, wav.readUnsignedByte())
            }
            assertTrue(File(tornDir, "recovered.txt").readText().contains("1 persisted samples"))
            assertEquals(44L, empty.file.length())
            assertTrue(File(emptyDir, "recovered.txt").readText().contains("0 persisted samples"))
            val repairedHash = sha(torn.file)
            RealtimeService.recover(sandbox)
            assertEquals("Idempotent repair", repairedHash, sha(torn.file))
            assertEquals(originalSha, sha(done.file))
        } finally { sandbox.deleteRecursively() }
    }

    @Test fun foregroundMicrophoneScreenOff() {
        val seconds = args.getString("micSeconds", "20")!!.toInt().coerceIn(15, 3600)
        // Host adb controls HOME/screen-off. Magic UI disconnects UiAutomation on screen-off;
        // keeping a cached UiAutomation here crashes AndroidJUnitRunner during finish().
        val power = context.getSystemService(android.os.PowerManager::class.java)
        val began = SystemClock.elapsedRealtime()
        try {
            context.startForegroundService(Intent(context, RealtimeService::class.java).putExtra("captureOnly", true).putExtra("seconds", seconds))
            val ready = SystemClock.elapsedRealtime() + 15000
            while (RealtimeService.view.value.status != "CAPTURE_ONLY" && SystemClock.elapsedRealtime() < ready) SystemClock.sleep(100)
            assertEquals("Foreground capture did not start", "CAPTURE_ONLY", RealtimeService.view.value.status)
            val manager = context.getSystemService(android.app.ActivityManager::class.java)
            assertTrue("No foreground service", manager.getRunningServices(20).any {
                it.service.className == RealtimeService::class.java.name && it.foreground })
            var observedOff = false
            val deadline = began + (seconds + 15) * 1000L
            while (RealtimeService.view.value.status == "CAPTURE_ONLY" && SystemClock.elapsedRealtime() < deadline) {
                observedOff = observedOff || !power.isInteractive
                SystemClock.sleep(500)
            }
            assertTrue("Host never turned the screen off", observedOff)
            assertEquals("CAPTURE_ONLY_COMPLETE", RealtimeService.view.value.status)
            val file = File(context.filesDir, "realtime-microphone-screenoff.json")
            val metrics = JSONObject(file.readText())
            assertEquals("PASS", metrics.getString("status"))
            val samples = metrics.getLong("samples")
            assertTrue("Capture lost >1 second of samples", samples >= (seconds - 1) * 16000L)
            assertEquals(44 + samples * 2, metrics.getLong("wav_bytes"))
            metrics.put("invocation", args.getString("invocation")).put("wall_ms", SystemClock.elapsedRealtime() - began)
                .put("requested_seconds", seconds).put("screen_off", true).put("foreground_verified", true)
            file.writeText(metrics.toString(2))
        } finally {
            context.startService(Intent(context, RealtimeService::class.java).setAction("STOP"))
        }
    }
}
