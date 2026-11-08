package ru.neurostenographer.core

import java.io.BufferedInputStream
import java.io.DataInputStream
import java.io.File
import java.io.FileInputStream
import java.io.RandomAccessFile

/** Validated, private PCM file with bounded reads. The complete recording is never
 * expanded into floats merely to inspect its duration or read one ASR/diarization block. */
class PcmFileAudio(val file: File, checkCancelled: () -> Unit = {}) {
    val sampleRate: Int
    val channels: Int
    val frames: Long
    val durationMs: Long
    private val dataOffset: Long
    private val fileBytes: Long

    init {
        var rate = 0
        var count = 0
        var samples = 0L
        var offset = -1L
        fileBytes = file.length()
        require(fileBytes <= MAX_ENCODED_BYTES) { "Аудиофайл слишком большой (максимум 5 ГБ)" }
        RandomAccessFile(file, "r").use { input ->
            fun tag() = String(ByteArray(4).also(input::readFully), Charsets.US_ASCII)
            fun u16() = input.readUnsignedByte() or (input.readUnsignedByte() shl 8)
            fun u32() = (0..3).sumOf { input.readUnsignedByte().toLong() shl (8 * it) }
            require(input.length() == fileBytes) { "Аудиофайл изменился" }
            val container = tag()
            require(container == "RIFF" || container == "RF64") { "Нужен PCM16 WAV (RIFF/RF64)" }
            val riff = u32()
            require(tag() == "WAVE") { "Нужен WAV" }
            var rf64Data = -1L
            if (container == "RF64") {
                require(riff == 0xffffffffL && tag() == "ds64") { "Нет размера RF64" }
                val dsSize = u32()
                require(dsSize in 28..4096 && 20 + dsSize <= fileBytes) { "Неверный ds64" }
                fun u64(): Long { val low = u32(); val high = u32(); require(high <= 1); return low or (high shl 32) }
                require(u64() + 8 == fileBytes) { "Повреждённый размер RF64" }
                rf64Data = u64()
                u64() // sample count; actual frame count is validated from data/format.
                require(u32() == 0L) { "Таблица дополнительных RF64 chunks не поддерживается" }
                input.seek(20 + dsSize + dsSize % 2)
            } else require(riff >= 36 && riff + 8 == fileBytes) { "Повреждённый размер WAV RIFF" }
            var formatSeen = false
            while (input.filePointer < fileBytes) {
                checkCancelled()
                require(fileBytes - input.filePointer >= 8) { "Обрезанный WAV chunk" }
                val kind = tag()
                val declared = u32()
                val size = if (kind == "data" && declared == 0xffffffffL && rf64Data >= 0) rf64Data else declared
                val start = input.filePointer
                val end = start + size + size % 2
                require(end <= fileBytes) { "Повреждённый размер WAV chunk" }
                when (kind) {
                    "fmt " -> {
                        require(!formatSeen && size in 16..4096 && u16() == 1) { "Нужен несжатый PCM16 WAV" }
                        count = u16(); rate = u32().toInt()
                        val byteRate = u32(); val alignment = u16(); val bits = u16()
                        require(count in 1..2 && rate in 8000..48000 && bits == 16 &&
                            alignment == count * 2 && byteRate == rate.toLong() * alignment) { "Нужен PCM16 WAV, 1–2 канала, 8–48 кГц" }
                        formatSeen = true
                    }
                    "data" -> {
                        require(formatSeen && offset < 0 && size > 0 && size % (count * 2) == 0L) { "Неверный WAV data" }
                        samples = size / (count * 2)
                        require(samples <= rate.toLong() * MAX_FILE_SECONDS) { "Максимум $MAX_FILE_LABEL" }
                        offset = start
                    }
                }
                input.seek(end)
            }
            require(offset >= 0 && samples * 1000 / rate >= 100) { "В WAV отсутствует звук длительностью хотя бы 0,1 с" }
            checkCancelled()
        }
        sampleRate = rate; channels = count; frames = samples; dataOffset = offset
        durationMs = frames * 1000 / sampleRate
    }

    /** Exact global linear-resampling positions, including reads across non-integer
     * 44.1 kHz boundaries. Adjacent ranges concatenate to the ordinary reader's output. */
    fun read(startMs: Long = 0, endMs: Long = durationMs, checkCancelled: () -> Unit = {}): PcmAudio {
        require(startMs >= 0 && endMs in (startMs + 1)..durationMs &&
            endMs - startMs <= PcmWav.MAX_SECONDS * 1000L) { "Слишком большой блок аудио" }
        require(file.length() == fileBytes) { "Аудиофайл изменился после проверки" }
        val firstOutput = startMs * 16
        val lastOutput = if (endMs == durationMs) frames * 16000 / sampleRate else endMs * 16
        val size = (lastOutput - firstOutput).toInt()
        val firstFrame = firstOutput * sampleRate / 16000
        FileInputStream(file).use { raw ->
            raw.channel.position(dataOffset + firstFrame * channels * 2)
            val input = DataInputStream(BufferedInputStream(raw, 64 * 1024))
            var position = firstFrame
            fun frame(at: Long): Float {
                if (at >= frames) return 0f
                var value = 0f
                repeat(channels) {
                    value += (input.readUnsignedByte() or (input.readUnsignedByte() shl 8)).toShort() / 32768f
                }
                return value / channels
            }
            var left = frame(position)
            var right = if (position + 1 < frames) frame(position + 1) else left
            val output = FloatArray(size) { index ->
                if (index % 16000 == 0) checkCancelled()
                val source = (firstOutput + index).toDouble() * sampleRate / 16000
                val wanted = source.toLong()
                while (position < wanted) {
                    left = right; position++
                    right = if (position + 1 < frames) frame(position + 1) else left
                }
                val fraction = (source - wanted).toFloat()
                left * (1 - fraction) + right * fraction
            }
            checkCancelled()
            return PcmAudio(output, 16000)
        }
    }

    companion object {
        const val MAX_FILE_SECONDS = 8 * 60 * 60
        const val MAX_FILE_LABEL = "8 часов"
        const val MAX_ENCODED_BYTES = 5L * 1024 * 1024 * 1024
    }
}
