package ru.neurostenographer.core

import java.io.File
import java.io.RandomAccessFile
import java.nio.ByteBuffer

fun testPcmFileAudio() {
    val directory = kotlin.io.path.createTempDirectory("pcm-file-").toFile()
    try {
        for (rate in listOf(8000, 16000, 44100, 48000)) for (channels in 1..2) {
            val file = File(directory, "$rate-$channels.wav")
            Pcm16WavWriter(file, rate, channels).use { writer ->
                val pcm = ByteBuffer.allocate(rate * channels * 2)
                repeat(rate * channels) { index ->
                    val value = (index * 37 % 60001 - 30000).toShort()
                    pcm.put(value.toByte()); pcm.put((value.toInt() shr 8).toByte())
                }
                pcm.flip(); writer.append(pcm); writer.finish()
            }
            val expected = file.inputStream().use { PcmWav.read(it) }.samples
            val source = PcmFileAudio(file)
            check(source.durationMs == 1000L)
            check(source.read().samples.contentEquals(expected)) { "whole PCM parity $rate/$channels" }
            val parts = listOf(0L, 137L, 503L, 999L, 1000L).zipWithNext().flatMap { (start, end) ->
                source.read(start, end).samples.toList()
            }.toFloatArray()
            check(parts.contentEquals(expected)) { "global resampling parity $rate/$channels" }
            var stopped = false
            try { source.read(0, 500) { throw InterruptedException() } }
            catch (_: InterruptedException) { stopped = true }
            check(stopped)
        }
        val rf = File(directory, "rf64.wav")
        RandomAccessFile(rf, "rw").use { f ->
            fun le(value: Long, bytes: Int) { repeat(bytes) { f.write((value ushr (8 * it)).toInt() and 255) } }
            f.writeBytes("RF64"); le(0xffffffffL,4); f.writeBytes("WAVEds64"); le(28,4)
            le(32072,8); le(32000,8); le(16000,8); le(0,4)
            f.writeBytes("fmt "); le(16,4); le(1,2); le(1,2); le(16000,4); le(32000,4); le(2,2); le(16,2)
            f.writeBytes("data"); le(0xffffffffL,4); f.setLength(32080)
        }
        check(PcmFileAudio(rf).durationMs == 1000L)
        check(PcmFileAudio(rf).read().samples.all { it == 0f })
        RandomAccessFile(rf, "rw").use { it.seek(20); it.write(0) }
        check(runCatching { PcmFileAudio(rf) }.isFailure)
        check(PcmFileAudio.MAX_ENCODED_BYTES == 5L * 1024 * 1024 * 1024)
        // Sparse eight-hour file: read the end without allocating/reading an hour of floats.
        val long = File(directory, "hour.wav")
        val frames = 28800L * 16000
        RandomAccessFile(long, "rw").use { f ->
            fun le(value: Long, bytes: Int) { repeat(bytes) { f.write((value ushr (8 * it)).toInt() and 255) } }
            f.writeBytes("RIFF"); le(frames * 2 + 36, 4); f.writeBytes("WAVEfmt "); le(16, 4)
            le(1, 2); le(1, 2); le(16000, 4); le(32000, 4); le(2, 2); le(16, 2)
            f.writeBytes("data"); le(frames * 2, 4); f.setLength(44 + frames * 2)
            f.seek(f.length() - 2); le(16384, 2)
        }
        val source = PcmFileAudio(long)
        check(source.durationMs == 28_800_000L)
        val last = source.read(28_799_000, 28_800_000)
        check(last.samples.size == 16000 && last.samples.last() == 0.5f)
        try { source.read(); error("unbounded allocation accepted") } catch (_: IllegalArgumentException) { }
        RandomAccessFile(long, "rw").use { it.setLength(it.length() - 1) }
        try { source.read(0, 1000); error("changed source accepted") } catch (_: IllegalArgumentException) { }
        try { PcmFileAudio(long); error("truncated data accepted") } catch (_: IllegalArgumentException) { }
        println("PASS disk PCM: 8 whole/range parity cases, exact 44.1k boundaries, eight-hour tail, cancellation, truncation and bounded allocation")
    } finally { directory.deleteRecursively() }
}
