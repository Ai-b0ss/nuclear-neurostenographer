package ru.neurostenographer.core
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.io.ByteArrayOutputStream

/** Sequential PCM16 downmix/resampling; retains just one source frame across codec buffers. */
class StreamingPcm16(private val rate: Int, private val channels: Int) {
    init { require(rate in 8000..48000 && channels in 1..2) }
    private var frames = 0L
    private var outputs = 0L
    private var previous = 0.0
    private var finished = false
    private var pending: Int? = null
    private fun emit(out: ByteArrayOutputStream, value: Double) {
        val v = kotlin.math.round(value).toInt().coerceIn(-32768,32767)
        pending?.let { out.write(it and 255); out.write((it shr 8) and 255) }
        pending = v; outputs++
    }
    fun append(bytes: ByteBuffer): ByteArray {
        check(!finished)
        require(bytes.remaining() % (channels * 2) == 0)
        val input = bytes.duplicate().order(ByteOrder.LITTLE_ENDIAN)
        val out = ByteArrayOutputStream()
        while (input.hasRemaining()) {
            var current = 0.0
            repeat(channels) { current += input.short.toDouble() / channels }
            val index = frames++
            while (outputs * rate.toLong() <= index * 16000L) {
                val position = outputs * rate.toDouble() / 16000
                val fraction = if (index == 0L) 1.0 else position - (index - 1)
                emit(out, previous * (1 - fraction) + current * fraction)
            }
            previous = current
        }
        return out.toByteArray()
    }
    fun finish(): ByteArray {
        check(!finished); finished = true
        val out = ByteArrayOutputStream()
        val wanted = frames * 16000 / rate
        while (outputs < wanted) emit(out, previous)
        if (outputs == wanted) pending?.let { out.write(it and 255); out.write((it shr 8) and 255) }
        pending = null
        return out.toByteArray()
    }
}
