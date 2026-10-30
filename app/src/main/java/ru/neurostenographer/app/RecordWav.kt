package ru.neurostenographer.app

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.File
import java.io.RandomAccessFile
import java.util.concurrent.atomic.AtomicBoolean

/** Records local 16kHz mono PCM16 WAV. Never sends audio to the network. */
class RecordWav(private val output: File) {
    private val running = AtomicBoolean(false)
    @Volatile private var worker: Thread? = null
    @Volatile private var failure: Throwable? = null

    fun start() {
        check(running.compareAndSet(false, true)) { "Recording already active" }
        val min = AudioRecord.getMinBufferSize(
            16000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT
        )
        require(min > 0) { "Unsupported microphone configuration" }
        val audio = AudioRecord(MediaRecorder.AudioSource.MIC, 16000,
            AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, min * 4)
        try {
            require(audio.state == AudioRecord.STATE_INITIALIZED) { "Microphone initialization failed" }
            worker = Thread {
                try {
                    RandomAccessFile(output, "rw").use { wav ->
                        wav.setLength(0)
                        wav.write(ByteArray(44))
                        val buffer = ByteArray(min * 2)
                        audio.startRecording()
                        while (running.get()) {
                            val count = audio.read(buffer, 0, buffer.size)
                            if (count > 0) wav.write(buffer, 0, count)
                            else if (count < 0) error("AudioRecord.read failure: " + count)
                        }
                        writeHeader(wav, wav.length() - 44L)
                    }
                } catch (e: Throwable) { failure = e }
                finally {
                    try { audio.stop() } catch (_: Exception) { }
                    audio.release()
                    running.set(false)
                }
            }.apply { name = "NeuroWavRecorder"; start() }
        } catch (e: Throwable) {
            running.set(false)
            audio.release()
            throw e
        }
    }

    fun stop(): File {
        running.set(false)
        val thread = requireNotNull(worker) { "No recording started" }
        thread.join(5000L)
        check(!thread.isAlive) { "Recorder did not stop" }
        failure?.let { throw IllegalStateException("Recording failed", it) }
        check(output.length() > 44L) { "Recording was empty" }
        return output
    }

    private fun writeHeader(file: RandomAccessFile, pcmLength: Long) {
        require(pcmLength >= 0 && pcmLength < 0xffff_ffffL - 36L)
        file.seek(0)
        file.write("RIFF".toByteArray(Charsets.US_ASCII))
        writeLe32(file, pcmLength + 36L)
        file.write("WAVEfmt ".toByteArray(Charsets.US_ASCII))
        writeLe32(file, 16)
        writeLe16(file, 1)
        writeLe16(file, 1)
        writeLe32(file, 16000)
        writeLe32(file, 32000)
        writeLe16(file, 2)
        writeLe16(file, 16)
        file.write("data".toByteArray(Charsets.US_ASCII))
        writeLe32(file, pcmLength)
    }
    private fun writeLe16(file: RandomAccessFile, x: Int) {
        file.write(x and 255)
        file.write((x ushr 8) and 255)
    }
    private fun writeLe32(file: RandomAccessFile, x: Long) {
        for (i in 0..3) file.write(((x ushr (8 * i)) and 255L).toInt())
    }
}
