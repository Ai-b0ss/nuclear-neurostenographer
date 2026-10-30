package ru.neurostenographer.core

import java.io.ByteArrayInputStream
import java.io.InputStream
import kotlin.math.min

fun testPcmStreaming() {
    // Independent whole-array baseline, including fractional and end-frame interpolation.
    for (rate in listOf(8000, 11025, 16000, 22050, 44100, 48000)) {
        for (channels in 1..2) for (frames in listOf(1, 2, 13, rate + 7)) {
            val bytes = pcmFixture(rate, channels, frames)
            for (i in 0 until frames * channels) {
                val value = ((i * 7919 + 137) % 65536 - 32768).toShort().toInt()
                bytes[44 + i * 2] = value.toByte()
                bytes[45 + i * 2] = (value shr 8).toByte()
            }
            val mono = FloatArray(frames) { frame ->
                var sum = 0f
                repeat(channels) { ch ->
                    val offset = 44 + (frame * channels + ch) * 2
                    sum += ((bytes[offset].toInt() and 255) or (bytes[offset + 1].toInt() shl 8))
                        .toShort() / 32768f
                }
                sum / channels
            }
            val expected = if (rate == 16000) mono else FloatArray(frames * 16000 / rate) { i ->
                val pos = i.toDouble() * rate / 16000
                val left = pos.toInt()
                val fraction = (pos - left).toFloat()
                mono[left] * (1 - fraction) + mono[min(left + 1, mono.lastIndex)] * fraction
            }
            val actual = PcmWav.read(bytes.inputStream()).samples
            check(actual.contentEquals(expected)) { "PCM changed: $rate Hz / $channels ch / $frames frames" }
            if (frames > 2) {
                try { PcmWav.read(bytes.copyOf(bytes.size - 2).inputStream()); error("Truncated tail accepted") }
                catch (_: java.io.EOFException) { }
            }
        }
    }
    val bytes = pcmFixture(48000, 2, 48000 * 2)
    var singleReads = 0
    var bulkReads = 0
    var closed = false
    val source = ByteArrayInputStream(bytes)
    val provider = object : InputStream() {
        override fun read(): Int { singleReads++; return source.read() }
        override fun read(b: ByteArray, off: Int, len: Int): Int {
            bulkReads++
            return source.read(b, off, len)
        }
        override fun close() { closed = true }
    }
    check(PcmWav.read(provider).samples.size == 32000)
    check(singleReads == 0 && bulkReads < 10) { "Unbuffered PCM reads: $singleReads / $bulkReads" }
    check(!closed) { "Parser must not close caller-owned stream" }
    println("PASS streaming PCM: 48 exact parity cases, truncated tails, bounded bulk I/O, input ownership")
}
