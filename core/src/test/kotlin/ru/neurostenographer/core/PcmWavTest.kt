package ru.neurostenographer.core

import java.io.ByteArrayInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

fun testPcmWav() {
    fun wav(rate: Int = 16000, channels: Int = 1, samples: ShortArray = shortArrayOf(-32768, 0, 32767)): ByteArray {
        val data = samples.size * 2
        return ByteBuffer.allocate(44 + data).order(ByteOrder.LITTLE_ENDIAN).apply {
            put("RIFF".toByteArray()); putInt(36 + data); put("WAVEfmt ".toByteArray()); putInt(16)
            putShort(1); putShort(channels.toShort()); putInt(rate); putInt(rate * channels * 2)
            putShort((channels * 2).toShort()); putShort(16); put("data".toByteArray()); putInt(data)
            samples.forEach { putShort(it) }
        }.array()
    }
    fun read(bytes: ByteArray) = PcmWav.read(ByteArrayInputStream(bytes))
    val audio = read(wav())
    check(audio.sampleRate == 16000 && audio.samples.size == 3)
    check(audio.samples[0] == -1f && audio.samples[1] == 0f && audio.samples[2] > 0.999f)
    val stereo = read(wav(8000, 2, shortArrayOf(32767, -32767, 10000, 10000)))
    check(stereo.samples.size == 4 && stereo.samples[0] == 0f && stereo.samples[2] > 0.30f)
    fun rejected(bytes: ByteArray) {
        var failed = false
        try { read(bytes) } catch (_: Exception) { failed = true }
        check(failed) { "Invalid audio accepted" }
    }
    rejected(byteArrayOf(1, 2, 3))
    rejected(wav().copyOf(45))
    rejected(wav().also { it[20] = 3 }) // IEEE float is not PCM16
    rejected(wav().also { it[40] = 127 }) // Declared chunk exceeds RIFF
    rejected(wav(channels = 3))
    rejected(wav(rate = 96000))
    rejected(wav(samples = shortArrayOf()))
    println("PASS PCM16 limits, truncation, encoding, normalization, stereo/resampling")
}
