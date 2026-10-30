package ru.neurostenographer.core

import java.io.Closeable
import java.io.File
import java.io.RandomAccessFile
import java.nio.ByteBuffer

/** Bounded sink for decoder PCM16 LE. A successful finish is required before use.
 * close without finish deletes partial audio; caller owns the completed file.
 */
class Pcm16WavWriter(private val file: File, val sampleRate: Int, val channels: Int) : Closeable {
    private val output: RandomAccessFile
    private var bytes = 0L
    private var finished = false
    private var closed = false
    private val limit: Long

    init {
        require(sampleRate in 8000..48000 && channels in 1..2) { "Нужны 8–48 кГц и 1–2 канала" }
        limit = sampleRate.toLong() * channels * 2 * PcmWav.MAX_SECONDS
        output = RandomAccessFile(file, "rw")
        try { output.setLength(0); output.write(ByteArray(44)) }
        catch (e: Throwable) { output.close(); file.delete(); throw e }
    }

    fun append(pcm: ByteBuffer, checkCancelled: () -> Unit = {}) {
        check(!closed && !finished)
        require(pcm.remaining().toLong() <= limit - bytes) { "Максимум 120 секунд декодированного аудио" }
        val buffer = ByteArray(minOf(pcm.remaining(), 64 * 1024))
        while (pcm.hasRemaining()) {
            checkCancelled()
            val count = minOf(pcm.remaining(), buffer.size)
            pcm.get(buffer, 0, count)
            output.write(buffer, 0, count)
            bytes += count
        }
    }

    fun finish(): Long {
        check(!closed && !finished)
        require(bytes % (channels * 2) == 0L) { "Обрезанный PCM16 кадр" }
        val frames = bytes / (channels * 2)
        require(frames >= (sampleRate + 9) / 10) { "Аудио короче 0,1 секунды" }
        output.seek(0)
        fun text(value: String) = output.write(value.toByteArray(Charsets.US_ASCII))
        fun le(value: Long, count: Int) { repeat(count) { output.write((value ushr (it * 8)).toInt() and 255) } }
        text("RIFF"); le(bytes + 36, 4); text("WAVEfmt "); le(16, 4)
        le(1, 2); le(channels.toLong(), 2); le(sampleRate.toLong(), 4)
        le(sampleRate.toLong() * channels * 2, 4); le((channels * 2).toLong(), 2); le(16, 2)
        text("data"); le(bytes, 4)
        output.close()
        finished = true
        closed = true
        return frames * 1000 / sampleRate
    }

    override fun close() {
        try { if (!closed) output.close() }
        finally { closed = true; if (!finished) file.delete() }
    }
}
