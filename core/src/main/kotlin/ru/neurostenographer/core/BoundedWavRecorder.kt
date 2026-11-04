package ru.neurostenographer.core

import java.io.Closeable
import java.io.File
import java.nio.ByteBuffer
import java.util.concurrent.atomic.AtomicBoolean

/** PCM16 mono capture. read returns immediately: zero means no data yet,
 * a negative count is a device error. The recorder owns close after start.
 */
interface PcmCapture : Closeable {
    fun start()
    fun read(samples: ShortArray): Int
}

class RecorderStopTimeout : IllegalStateException("Микрофон ещё останавливается. Повторите остановку.")

/** One-shot 16 kHz recorder. Output is a new, app-owned empty file.
 * Only the writer thread reads/closes a started capture. A stop timeout retains
 * ownership; callers must not clear the recorder or delete its output yet.
 */
class BoundedWavRecorder(private val output: File, private val capture: PcmCapture) {
    private val stopping = AtomicBoolean(false)
    @Volatile private var worker: Thread? = null
    @Volatile private var failure: Throwable? = null
    private var started = false
    val isRunning: Boolean get() = worker?.isAlive == true

    @Synchronized fun start() {
        check(!started) { "Recorder is one-shot" }
        started = true
        try {
            require(output.isFile && output.length() == 0L) { "Recorder needs a new empty file" }
            capture.start()
            worker = Thread({ record() }, "NeuroWavRecorder").also { it.start() }
        } catch (e: Throwable) {
            try { capture.close() } catch (cleanup: Throwable) { e.addSuppressed(cleanup) }
            if (output.length() == 0L) output.delete()
            failure = e
            throw e
        }
    }

    fun requestStop() { stopping.set(true) }

    fun stop(timeoutMs: Long = 5000): File {
        require(timeoutMs > 0)
        requestStop()
        val thread = requireNotNull(worker) { "No recording started" }
        thread.join(timeoutMs)
        if (thread.isAlive) throw RecorderStopTimeout()
        failure?.let { throw IllegalStateException("Ошибка записи: ${it.message ?: it.javaClass.simpleName}", it) }
        check(output.isFile && output.length() >= 3244L) { "Запись короче 0,1 секунды" }
        return output
    }

    private fun record() {
        try {
            Pcm16WavWriter(output, 16000, 1).use { sink ->
                val samples = ShortArray(2048)
                val bytes = ByteArray(samples.size * 2)
                val limit = 16000L * PcmWav.MAX_SECONDS
                val beginning = System.nanoTime()
                var frames = 0L
                while (!stopping.get() && frames < limit &&
                    System.nanoTime() - beginning < PcmWav.MAX_SECONDS * 1_000_000_000L) {
                    val count = capture.read(samples)
                    check(count in 0..samples.size) { "AudioRecord.read failure: $count" }
                    if (count == 0) { Thread.sleep(10); continue }
                    val keep = minOf(count.toLong(), limit - frames).toInt()
                    for (i in 0 until keep) {
                        bytes[2 * i] = samples[i].toByte()
                        bytes[2 * i + 1] = (samples[i].toInt() shr 8).toByte()
                    }
                    sink.append(ByteBuffer.wrap(bytes, 0, keep * 2))
                    frames += keep
                }
                sink.finish()
            }
        } catch (e: Throwable) { failure = e }
        finally {
            try { capture.close() }
            catch (e: Throwable) {
                val previous = failure
                if (previous == null) failure = e else previous.addSuppressed(e)
            }
            if (failure != null) output.delete()
        }
    }
}
