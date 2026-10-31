package ru.neurostenographer.core

import java.io.ByteArrayInputStream
import java.io.InputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.util.concurrent.CancellationException

/** Full-container cases: accepting the first data chunk must not hide later corruption/audio. */
fun testWavContainer() {
    fun size(bytes: ByteArray, offset: Int, value: Int): ByteArray = bytes.also {
        ByteBuffer.wrap(it).order(ByteOrder.LITTLE_ENDIAN).putInt(offset, value)
    }
    fun chunk(tag: String, body: ByteArray): ByteArray =
        ByteBuffer.allocate(8 + body.size + body.size % 2).order(ByteOrder.LITTLE_ENDIAN).apply {
            put(tag.toByteArray(Charsets.US_ASCII)); putInt(body.size); put(body)
        }.array()
    val plain = pcmFixture()
    fun append(vararg chunks: ByteArray): ByteArray {
        val bytes = plain + chunks.reduce { a, b -> a + b }
        return size(bytes, 4, bytes.size - 8)
    }
    val metadata = append(chunk("LIST", byteArrayOf(1, 2, 3)), chunk("JUNK", ByteArray(8192)))
    val expected = PcmWav.read(plain.inputStream())
    val decoded = PcmWav.read(metadata.inputStream())
    check(decoded.samples.contentEquals(expected.samples))
    // Metadata before fmt/data, and odd-byte padding, remain legal.
    val before = (plain.copyOfRange(0, 12) + chunk("JUNK", byteArrayOf(7)) + plain.copyOfRange(12, plain.size))
        .let { size(it, 4, it.size - 8) }
    check(PcmWav.read(before.inputStream()).samples.contentEquals(expected.samples))
    var closed = false
    val fragmented = object : InputStream() {
        val source = ByteArrayInputStream(metadata)
        override fun read() = source.read()
        override fun read(b: ByteArray, off: Int, len: Int) = source.read(b, off, minOf(len, 3))
        override fun close() { closed = true }
    }
    check(PcmWav.read(fragmented).samples.contentEquals(expected.samples) && !closed)

    val bad = listOf(
        append(chunk("data", ByteArray(3200))), // Never silently transcribe only the first half.
        append(plain.copyOfRange(12, 36)), // Duplicate fmt after audio.
        append(chunk("LIST", ByteArray(32))).dropLast(1).toByteArray(), // Missing metadata tail.
        append(chunk("JUNK", byteArrayOf(1))).dropLast(1).toByteArray(), // Missing pad.
        append(byteArrayOf(1, 2, 3)), // RIFF ends in an incomplete chunk header.
        plain + byteArrayOf(0), // Unadvertised bytes after RIFF.
        size(plain.copyOf(), 4, plain.size - 6), // RIFF advertises bytes absent on source.
        size(plain.copyOf(), 4, plain.size - 10) // RIFF too short for data.
    )
    val root = Files.createTempDirectory("wav-container-test").toFile()
    try {
        val kept = AudioSnapshots.import(plain.inputStream(), root)
        for (bytes in bad) {
            check(runCatching { PcmWav.read(bytes.inputStream()) }.isFailure)
            check(runCatching { AudioSnapshots.import(bytes.inputStream(), root) }.isFailure)
            check(root.listFiles()!!.toList() == listOf(kept.file)) { "Rejected WAV leaked staged audio" }
            check(kept.file.readBytes().contentEquals(plain))
        }
        var polls = 0
        // Cancellation after PCM has been decoded, during trailing metadata validation.
        val result = runCatching { PcmWav.read(metadata.inputStream()) {
            if (++polls == 6) throw CancellationException()
        } }
        check(result.exceptionOrNull() is CancellationException)
    } finally { root.listFiles()?.forEach { it.delete() }; root.delete() }
    println("PASS WAV container: metadata/padding/fragmented reads, 8 corruption negatives, snapshot preservation, tail cancellation")
}
