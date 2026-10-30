package ru.neurostenographer.core

import java.io.ByteArrayInputStream
import java.io.InputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.util.concurrent.CancellationException

fun pcmFixture(rate: Int = 16000, channels: Int = 1, frames: Int = rate): ByteArray =
    ByteBuffer.allocate(44 + frames * channels * 2).order(ByteOrder.LITTLE_ENDIAN).apply {
        put("RIFF".toByteArray()); putInt(capacity() - 8); put("WAVEfmt ".toByteArray()); putInt(16)
        putShort(1); putShort(channels.toShort()); putInt(rate); putInt(rate * channels * 2)
        putShort((channels * 2).toShort()); putShort(16); put("data".toByteArray()); putInt(capacity() - 44)
        repeat(frames * channels) { putShort(if (it % 2 == 0) 1000 else -1000) }
    }.array()

fun testAudioSnapshots() {
    val root = Files.createTempDirectory("audio-snapshot-test").toFile()
    try {
        // Realistic one-second phone recording and imported 44.1 kHz stereo WAV.
        val original = AudioSnapshots.import(pcmFixture().inputStream(), root)
        check(original.durationMs == 1000L)
        val source = pcmFixture(44100, 2)
        val imported = AudioSnapshots.import(source.inputStream(), root)
        source.fill(0) // Later provider mutation must not change selected bytes.
        val normalized = imported.file.inputStream().use { PcmWav.read(it) }
        check(normalized.durationMs == 1000L && normalized.samples.size == 16000)
        val kept = root.listFiles()!!.toSet()
        fun rejected(input: InputStream, cancel: () -> Unit = {}) {
            var failed = false
            try { input.use { AudioSnapshots.import(it, root, cancel) } }
            catch (_: Exception) { failed = true }
            check(failed)
            check(root.listFiles()!!.toSet() == kept) { "Failed import leaked a staged recording" }
            check(original.file.inputStream().use { PcmWav.read(it) }.durationMs == 1000L)
        }
        rejected(ByteArrayInputStream(byteArrayOf(1, 2, 3))) // MP3/unknown is not WAV
        rejected(pcmFixture().copyOf(100).inputStream()) // provider truncation
        rejected(pcmFixture(frames = 1599).inputStream()) // <100 ms
        rejected(pcmFixture(frames = 16000 * 121).inputStream()) // >120 seconds
        rejected(object : InputStream() {
            override fun read(): Int = error("Provider disconnected")
        })
        rejected(object : InputStream() { // no allocation of a huge adversarial source
            override fun read(): Int = 0
            override fun read(b: ByteArray, off: Int, len: Int): Int { b.fill(0); return len }
        })
        var reads = 0
        rejected(pcmFixture().inputStream()) { if (++reads == 2) throw CancellationException() }
        try {
            PcmWav.read(pcmFixture().inputStream()) { throw CancellationException() }
            error("WAV parser ignored cancellation")
        } catch (_: CancellationException) { }
        println("PASS audio snapshots: recording/import, stereo 44.1k, changed provider, malformed/short/long/oversize/disconnected/cancelled input")
    } finally { root.listFiles()?.forEach { it.delete() }; root.delete() }
}
