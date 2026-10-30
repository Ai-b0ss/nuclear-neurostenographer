package ru.neurostenographer.core

import java.io.File
import java.nio.file.Files
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

/** Generated numeric PCM and fake device faults; never microphone/ASR evidence. */
fun testBoundedWavRecorder() {
    val root = Files.createTempDirectory("recorder-").toFile()
    fun fresh() = File.createTempFile("recording_", ".wav", root)
    fun await(latch: CountDownLatch) = check(latch.await(5, TimeUnit.SECONDS)) { "Test worker timed out" }
    fun finished(recorder: BoundedWavRecorder) {
        val deadline = System.nanoTime() + 5_000_000_000L
        while (recorder.isRunning && System.nanoTime() < deadline) Thread.sleep(1)
        check(!recorder.isRunning) { "Test recorder did not finish" }
    }
    var cases = 0
    try {
        // Intermittent no-data is normal. Exact signed PCM must survive LE writing.
        val first = CountDownLatch(1)
        val secondRead = CountDownLatch(1)
        val closed = AtomicInteger()
        var reads = 0
        val file = fresh()
        val recorder = BoundedWavRecorder(file, object : PcmCapture {
            override fun start() { }
            override fun read(samples: ShortArray): Int {
                reads++
                if (reads == 1) return 0
                if (reads == 2) {
                    for (i in samples.indices) samples[i] = (i * 83 - 32768).toShort()
                    first.countDown()
                    return samples.size
                }
                secondRead.countDown()
                return 0
            }
            override fun close() { closed.incrementAndGet() }
        })
        recorder.start(); await(first); await(secondRead)
        check(recorder.stop() == file && recorder.stop() == file)
        check(closed.get() == 1 && !recorder.isRunning)
        val audio = file.inputStream().use { PcmWav.read(it) }
        check(audio.samples.size == 2048)
        audio.samples.forEachIndexed { i, value -> check(value == (i * 83 - 32768).toShort() / 32768f) }
        check(runCatching { recorder.start() }.isFailure)
        cases++

        // Device failures, impossible counts and <100ms capture remove partial output.
        for (bad in listOf(-6, -3, 2049, 0)) {
            val output = fresh()
            var count = 0
            val calls = AtomicInteger()
            val nextRead = CountDownLatch(1)
            val session = BoundedWavRecorder(output, object : PcmCapture {
                override fun start() { }
                override fun read(samples: ShortArray): Int {
                    count++
                    if (count == 1) return if (bad == 0) 800 else samples.size
                    nextRead.countDown()
                    return bad
                }
                override fun close() { calls.incrementAndGet() }
            })
            session.start(); await(nextRead)
            if (bad == 0) session.requestStop()
            finished(session)
            check(runCatching { session.stop() }.isFailure)
            check(!output.exists() && calls.get() == 1)
            cases++
        }

        // Failure during start still releases the capture, without leaking an empty file.
        val startOutput = fresh()
        val startClosed = AtomicInteger()
        val startFailure = BoundedWavRecorder(startOutput, object : PcmCapture {
            override fun start(): Unit = error("device policy denied capture")
            override fun read(samples: ShortArray): Int = error("must never read")
            override fun close() { startClosed.incrementAndGet() }
        })
        check(runCatching { startFailure.start() }.isFailure)
        check(!startFailure.isRunning && !startOutput.exists() && startClosed.get() == 1)
        cases++

        // Valid output is not accepted if capture cleanup fails.
        val releaseOutput = fresh()
        val releaseRead = CountDownLatch(1)
        var releasedReads = 0
        val releaseFailure = BoundedWavRecorder(releaseOutput, object : PcmCapture {
            override fun start() { }
            override fun read(samples: ShortArray): Int {
                if (releasedReads++ == 0) return samples.size
                releaseRead.countDown(); return 0
            }
            override fun close(): Unit = error("release failed")
        })
        releaseFailure.start(); await(releaseRead)
        check(runCatching { releaseFailure.stop() }.isFailure && !releaseOutput.exists())
        cases++

        // Simulate a broken native driver ignoring nonblocking mode. Timeout is
        // explicit, no concurrent release or deletion; retry joins the same owner.
        val blockedOutput = fresh()
        val entered = CountDownLatch(1)
        val unblock = CountDownLatch(1)
        val blockedClosed = AtomicInteger()
        val blocked = BoundedWavRecorder(blockedOutput, object : PcmCapture {
            override fun start() { }
            override fun read(samples: ShortArray): Int {
                entered.countDown(); await(unblock)
                return samples.size
            }
            override fun close() { blockedClosed.incrementAndGet() }
        })
        blocked.start(); await(entered)
        try {
            check(runCatching { blocked.stop(20) }.exceptionOrNull() is RecorderStopTimeout)
            check(blocked.isRunning && blockedOutput.isFile && blockedClosed.get() == 0)
        } finally { unblock.countDown() }
        check(blocked.stop() == blockedOutput && !blocked.isRunning && blockedClosed.get() == 1)
        cases++

        // Fast generated data hits the exact sample cap, no wall-clock wait/padding.
        val limitOutput = fresh()
        val limitClosed = AtomicInteger()
        val limit = BoundedWavRecorder(limitOutput, object : PcmCapture {
            override fun start() { }
            override fun read(samples: ShortArray): Int = samples.size
            override fun close() { limitClosed.incrementAndGet() }
        })
        limit.start(); finished(limit)
        check(limit.stop().length() == 44L + 120 * 32000)
        check(limitOutput.inputStream().use { PcmWav.read(it) }.durationMs == 120_000L)
        check(limitClosed.get() == 1)
        cases++
        check(cases == 9)
        println("PASS bounded recorder ($cases capture/cleanup/timeout/PCM cases; fake capture only)")
    } finally {
        root.listFiles().orEmpty().forEach { it.delete() }
        root.delete()
    }
}
