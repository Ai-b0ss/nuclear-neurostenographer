package ru.neurostenographer.core

import java.io.File
import java.nio.ByteBuffer
import kotlin.random.Random

fun testPcm16WavWriter() {
    val root = java.nio.file.Files.createTempDirectory("wav-writer-").toFile()
    try {
        var cases = 0
        for (rate in listOf(8000, 16000, 44100, 48000)) for (channels in 1..2) {
            val frames = rate / 4
            val random = Random(rate + channels)
            val bytes = ByteArray(frames * channels * 2).also(random::nextBytes)
            val file = File(root, "output.wav")
            Pcm16WavWriter(file, rate, channels).use { sink ->
                // Odd, offset, fragmented buffers exercise real codec BufferInfo boundaries.
                var offset = 0
                while (offset < bytes.size) {
                    val n = minOf(bytes.size - offset, random.nextInt(1, 4100))
                    val buffer = ByteBuffer.allocate(n + 13)
                    buffer.position(7); buffer.put(bytes, offset, n)
                    buffer.limit(7 + n); buffer.position(7)
                    sink.append(buffer)
                    check(buffer.remaining() == 0)
                    offset += n
                }
                check(sink.finish() == frames * 1000L / rate)
                check(runCatching { sink.append(ByteBuffer.wrap(byteArrayOf(0))) }.isFailure)
            }
            check(file.readBytes().drop(44).toByteArray().contentEquals(bytes))
            val audio = file.inputStream().use { PcmWav.read(it) }
            check(audio.durationMs in 249..250 && audio.sampleRate == 16000)
            if (rate == 16000) for (i in audio.samples.indices) {
                var expected = 0f
                repeat(channels) { ch ->
                    val index = (i * channels + ch) * 2
                    val sample = ((bytes[index].toInt() and 255) or (bytes[index + 1].toInt() shl 8)).toShort()
                    expected += sample / 32768f
                }
                check(audio.samples[i] == expected / channels)
            }
            file.delete(); cases++
        }
        fun rejects(name: String, action: (Pcm16WavWriter) -> Unit) {
            val file = File(root, name)
            check(runCatching { Pcm16WavWriter(file, 16000, 1).use(action) }.isFailure)
            check(!file.exists()) { "Partial audio retained: $name" }
        }
        rejects("empty.wav") { it.finish() }
        rejects("short.wav") { it.append(ByteBuffer.wrap(ByteArray(3198))); it.finish() }
        rejects("partial.wav") { it.append(ByteBuffer.wrap(ByteArray(3201))); it.finish() }
        rejects("cancel.wav") { it.append(ByteBuffer.wrap(ByteArray(64000))) { error("cancelled") } }
        rejects("long.wav") { it.append(ByteBuffer.wrap(ByteArray(16000 * 2 * 120 + 2))) }
        val abandoned = File(root, "abandoned.wav")
        Pcm16WavWriter(abandoned, 16000, 1).use { it.append(ByteBuffer.wrap(ByteArray(3200))) }
        check(!abandoned.exists())
        val limit = File(root, "limit.wav")
        Pcm16WavWriter(limit, 8000, 2).use { sink ->
            repeat(120) { sink.append(ByteBuffer.wrap(ByteArray(8000 * 4))) }
            check(sink.finish() == 120000L)
        }
        check(limit.inputStream().use { PcmWav.read(it).durationMs } == 120000L)
        limit.delete()
        for ((rate, channels) in listOf(7999 to 1, 48001 to 1, 16000 to 0, 16000 to 3)) {
            val bad = File(root, "invalid.wav")
            check(runCatching { Pcm16WavWriter(bad, rate, channels) }.isFailure)
            check(!bad.exists())
        }
        for (rate in listOf(8000, 16000, 44100, 48000)) for (channels in 1..2) {
            val clock = DecodedPcmTimeline(rate, channels)
            // Normalize a negative codec origin; permit rounding at buffer boundaries.
            repeat(100) { clock.accept(1000 * channels * 2, -23000L + it * 1000L * 1_000_000 / rate) }
        }
        val clock = DecodedPcmTimeline(16000, 1)
        clock.accept(3200, 500_000)
        for ((bytes, pts) in listOf(3200 to 800_001L, 3200 to 399_999L, 3 to 600_000L, 0 to 600_000L)) {
            check(runCatching { clock.accept(bytes, pts) }.isFailure)
        }
        clock.accept(3200, 600_000) // Rejections must not advance the accepted timeline.
        val overflow = DecodedPcmTimeline(16000, 1)
        overflow.accept(3200, Long.MIN_VALUE)
        check(runCatching { overflow.accept(3200, Long.MAX_VALUE) }.isFailure)
        val maxClock = DecodedPcmTimeline(8000, 2)
        maxClock.accept(8000 * 4 * 120, 0)
        check(runCatching { maxClock.accept(4, 120_000_000) }.isFailure)
        println("PASS PCM16 writer: $cases roundtrips, exact bounds, partial/cancel/error cleanup")
    } finally {
        root.listFiles()?.forEach { it.delete() }; root.delete()
    }
}
