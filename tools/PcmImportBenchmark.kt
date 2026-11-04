package ru.neurostenographer.tools

import com.sun.management.ThreadMXBean
import java.lang.management.ManagementFactory
import java.io.ByteArrayInputStream
import java.io.InputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.io.File
import ru.neurostenographer.core.PcmWav
import ru.neurostenographer.baseline.PcmWav as BaselinePcmWav

/** Generated numeric PCM, not speech or a model quality/performance benchmark. */
fun main(args: Array<String>) {
    val rate = 48000
    val frames = rate * 120
    val bytes = ByteBuffer.allocate(44 + frames * 4).order(ByteOrder.LITTLE_ENDIAN).apply {
        put("RIFF".toByteArray()); putInt(capacity() - 8); put("WAVEfmt ".toByteArray()); putInt(16)
        putShort(1); putShort(2); putInt(rate); putInt(rate * 4); putShort(4); putShort(16)
        put("data".toByteArray()); putInt(capacity() - 44)
        repeat(frames) { putShort((it % 32768).toShort()); putShort((-it % 32768).toShort()) }
    }.array()
    val bean = ManagementFactory.getThreadMXBean() as ThreadMXBean
    check(bean.isThreadAllocatedMemorySupported)
    bean.isThreadAllocatedMemoryEnabled = true
    fun measure(baseline: Boolean): Pair<FloatArray, String> {
        var single = 0L
        var bulk = 0L
        val data = ByteArrayInputStream(bytes)
        val source = object : InputStream() {
            override fun read(): Int { single++; return data.read() }
            override fun read(b: ByteArray, off: Int, len: Int): Int { bulk++; return data.read(b, off, len) }
        }
        val allocated = bean.getThreadAllocatedBytes(Thread.currentThread().id)
        val start = System.nanoTime()
        val pcm = if (baseline) BaselinePcmWav.read(source).samples else PcmWav.read(source).samples
        val elapsed = System.nanoTime() - start
        val delta = bean.getThreadAllocatedBytes(Thread.currentThread().id) - allocated
        return pcm to "{\"elapsed_ns\":$elapsed,\"thread_allocated_bytes\":$delta,\"single_source_reads\":$single,\"bulk_source_reads\":$bulk,\"output_samples\":${pcm.size}}"
    }
    // Warm classes/JIT; allocations then measured on the same generated 120s stereo input.
    measure(true); measure(false)
    val (old, before) = measure(true)
    val (new, after) = measure(false)
    check(old.contentEquals(new) && new.size == 120 * 16000)
    File(args.single()).writeText("{\"platform\":\"Windows JDK17 host; Android NOT_RUN\",\"fixture\":\"generated numeric PCM16 48kHz stereo 120s, not speech\",\"scope\":\"parser only; in-memory source counters and current-thread allocations, not process peak RAM or ASR RTF\",\"exact_pcm_parity\":true,\"baseline\":$before,\"streaming\":$after}\n")
}
