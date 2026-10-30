package ru.neurostenographer.core

import java.io.DataInputStream
import java.io.BufferedInputStream
import java.io.InputStream
import kotlin.math.min

data class PcmAudio(val samples: FloatArray, val sampleRate: Int) {
    val durationMs: Long get() = samples.size * 1000L / sampleRate
}

/** Bounded PCM16 RIFF reader. Reject unsupported encodings rather than feeding noise to ASR. */
object PcmWav {
    const val MAX_SECONDS = 120
    fun read(input: InputStream, checkCancelled: () -> Unit = {}): PcmAudio {
        // Providers/files may otherwise perform one read syscall per PCM byte.
        // Caller retains ownership of the input; this wrapper is not closed here.
        val stream = DataInputStream(BufferedInputStream(input, 64 * 1024))
        fun tag(): String = String(ByteArray(4).also(stream::readFully), Charsets.US_ASCII)
        fun u16(): Int = stream.readUnsignedByte() or (stream.readUnsignedByte() shl 8)
        fun u32(): Long = (0..3).sumOf { stream.readUnsignedByte().toLong() shl (8 * it) }
        fun skip(count: Long) {
            var left = count
            val buffer = ByteArray(4096)
            while (left > 0) {
                checkCancelled()
                val read = stream.read(buffer, 0, min(left, buffer.size.toLong()).toInt())
                require(read > 0) { "Обрезанный WAV" }
                left -= read
            }
        }
        require(tag() == "RIFF") { "Нужен PCM16 WAV (RIFF)" }
        val riffSize = u32()
        require(riffSize in 36..(48_000L * 4 * MAX_SECONDS + 1_048_576)) { "WAV слишком большой" }
        require(tag() == "WAVE") { "Не WAV" }
        var remaining = riffSize - 4
        var rate = 0
        var channels = 0
        var sawFormat = false
        var audio: PcmAudio? = null
        while (remaining >= 8) {
            checkCancelled()
            val id = tag()
            val size = u32()
            remaining -= 8
            val padded = size + size % 2
            require(padded <= remaining) { "Повреждённый размер WAV chunk" }
            when (id) {
                "fmt " -> {
                    require(!sawFormat && size in 16..4096) { "Неверный WAV fmt" }
                    require(u16() == 1) { "Поддерживается только несжатый PCM16 WAV" }
                    channels = u16()
                    rate = u32().toInt()
                    val byteRate = u32()
                    val blockAlign = u16()
                    val bits = u16()
                    require(channels in 1..2 && rate in 8000..48000 && bits == 16 &&
                        blockAlign == channels * 2 && byteRate == rate.toLong() * blockAlign) {
                        "Нужен PCM16 WAV, 1–2 канала, 8–48 кГц"
                    }
                    skip(size - 16)
                    sawFormat = true
                }
                "data" -> {
                    require(audio == null) { "Несколько WAV data: преобразуйте запись в один PCM16 поток" }
                    require(sawFormat && size > 0 && size % (channels * 2) == 0L) { "Неверный WAV data" }
                    val frames = size / (channels * 2)
                    require(frames <= rate.toLong() * MAX_SECONDS) { "Максимум $MAX_SECONDS секунд" }
                    var framesRead = 0
                    fun readFrame(): Float {
                        if (framesRead++ % 16000 == 0) checkCancelled()
                        var value = 0f
                        repeat(channels) { value += u16().toShort() / 32768f }
                        return value / channels
                    }
                    if (rate == 16000) {
                        audio = PcmAudio(FloatArray(frames.toInt()) { readFrame() }, rate)
                    } else {
                        // Keep only two source frames, rather than up to 23 MB of source floats.
                        // Linear resampling remains a baseline, not a band-limited decoder.
                        var frame = 0
                        var leftValue = readFrame()
                        var rightValue = if (frames > 1) readFrame() else leftValue
                        val output = FloatArray((frames * 16000 / rate).toInt()) { i ->
                            if (i % 16000 == 0) checkCancelled()
                            val pos = i.toDouble() * rate / 16000
                            val left = pos.toInt()
                            val fraction = (pos - left).toFloat()
                            while (frame < left) {
                                leftValue = rightValue
                                frame++
                                rightValue = if (framesRead < frames) readFrame() else leftValue
                            }
                            leftValue * (1 - fraction) + rightValue * fraction
                        }
                        // Downsampling can leave a final source frame unused: still detect truncation.
                        while (framesRead < frames) readFrame()
                        audio = PcmAudio(output, 16000)
                    }
                }
                else -> skip(size)
            }
            if (size % 2 == 1L) stream.readUnsignedByte()
            remaining -= padded
        }
        require(remaining == 0L) { "Обрезанный заголовок WAV chunk" }
        checkCancelled()
        require(stream.read() == -1) { "Данные за пределами WAV RIFF; преобразуйте файл в PCM16 WAV" }
        return requireNotNull(audio) { "В WAV отсутствует audio data" }
    }
}
