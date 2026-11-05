package ru.neurostenographer.app

import ru.neurostenographer.core.*
import java.io.Closeable
import java.io.File
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Single capture writer and single inference reader; durable PCM is the overflow path.
 * No queue/model lock on capture. Audio is private and retained for recovery/batch fallback. */
class RealtimeJournal(val file: File) : Closeable {
    private val writer: Pcm16WavWriter
    private val reader: RandomAccessFile
    init {
        require(!file.exists()) { "Realtime capture needs a new file; existing audio is never replaced" }
        writer = Pcm16WavWriter(file, 16000, 1, maxSeconds = 3600, preservePartialOnFailure = true)
        reader = RandomAccessFile(file, "r")
    }
    private val ring = RealtimeRing()
    @Volatile var samples = 0L
        private set
    @Volatile var done = false
        private set
    @Volatile var failure: String? = null
    val startedNs = System.nanoTime()
    var diskReads = 0
        private set
    fun append(input: ShortArray, count: Int) {
        check(!done)
        val bytes = ByteBuffer.allocate(count * 2).order(ByteOrder.LITTLE_ENDIAN)
        for (i in 0 until count) bytes.putShort(input[i])
        bytes.flip()
        writer.append(bytes)
        ring.append(input, count)
        samples += count
    }
    fun finish() {
        try {
            writer.finish()
            File(file.parentFile, "capture-finalized.txt").writeText(samples.toString())
        } finally { done = true }
    }
    fun read(start: Long, count: Int): FloatArray {
        require(start >= 0 && count >= 0 && start + count <= samples)
        ring.read(start, count)?.let { return it }
        diskReads++
        val bytes = ByteArray(count * 2)
        reader.seek(44 + start * 2); reader.readFully(bytes)
        val shorts = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
        return FloatArray(count) { shorts.get() / 32768f }
    }
    override fun close() { reader.close(); writer.close() }

    companion object {
        /** Recover only this feature's own unfinished PCM16 file after process death.
         * No invented missing samples: header reflects the bytes actually on disk. */
        fun recover(file: File): Long {
            require(file.name == "capture.wav" && file.parentFile?.parentFile?.name == "realtime")
            RandomAccessFile(file, "rw").use { out ->
                require(out.length() in 3244..(44 + 3600L * 32000))
                val bytes = (out.length() - 44) / 2 * 2
                out.setLength(bytes + 44); out.seek(0)
                val header = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN).apply {
                    put("RIFF".toByteArray()); putInt((bytes + 36).toInt()); put("WAVEfmt ".toByteArray()); putInt(16)
                    putShort(1); putShort(1); putInt(16000); putInt(32000); putShort(2); putShort(16)
                    put("data".toByteArray()); putInt(bytes.toInt())
                }.array()
                out.write(header); out.fd.sync()
                return bytes / 2
            }
        }
    }
}
