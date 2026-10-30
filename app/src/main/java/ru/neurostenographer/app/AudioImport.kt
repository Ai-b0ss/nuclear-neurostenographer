package ru.neurostenographer.app

import android.content.Context
import android.media.AudioFormat
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.net.Uri
import android.os.SystemClock
import ru.neurostenographer.core.*
import java.io.File

/** Provider bytes are bounded and snapshotted before native parsers see them.
 * No URLs reach MediaExtractor; it only opens an owned local file.
 */
object AudioImport {
    private val codecs = setOf("audio/mpeg", "audio/mp4a-latm", "audio/vorbis", "audio/opus",
        "audio/flac", "audio/3gpp", "audio/amr-wb")

    fun import(context: Context, uri: Uri, checkCancelled: () -> Unit = {}): AudioSnapshot {
        require(uri.scheme == "content" || uri.scheme == "file") { "Выберите локальный аудиодокумент" }
        val directory = File(context.cacheDir, "audio-input")
        check(directory.isDirectory || directory.mkdirs())
        val source = File.createTempFile("encoded-", ".input", directory)
        try {
            requireNotNull(context.contentResolver.openInputStream(uri)) { "Не удалось открыть аудио" }.use { input ->
                source.outputStream().buffered().use { output ->
                    val buffer = ByteArray(64 * 1024)
                    var total = 0L
                    while (true) {
                        checkCancelled()
                        val count = input.read(buffer)
                        if (count < 0) break
                        require(count > 0) { "Источник не возвращает данные" }
                        total += count
                        require(total <= AudioSnapshots.MAX_BYTES) { "Аудиофайл слишком большой (лимит около 24 МБ)" }
                        output.write(buffer, 0, count)
                    }
                }
            }
            checkCancelled()
            val riff = source.inputStream().use { input ->
                val magic = ByteArray(4)
                input.read(magic) == 4 && magic.contentEquals("RIFF".toByteArray(Charsets.US_ASCII))
            }
            // Strict WAV validation remains authoritative: do not bypass it via codec fallback.
            if (riff) return source.inputStream().use { AudioSnapshots.import(it, directory, checkCancelled) }
            return decode(source, directory, checkCancelled)
        } finally { source.delete() }
    }

    private fun decode(source: File, directory: File, checkCancelled: () -> Unit): AudioSnapshot {
        val destination = File.createTempFile("decoded-", ".wav", directory)
        var accepted = false
        val extractor = MediaExtractor()
        var decoder: MediaCodec? = null
        var writer: Pcm16WavWriter? = null
        try {
            extractor.setDataSource(source.absolutePath)
            val tracks = (0 until extractor.trackCount).filter {
                extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true
            }
            require(tracks.size == 1) { "Нужен ровно один аудиотрек" }
            val track = tracks.single()
            val format = extractor.getTrackFormat(track)
            val mime = requireNotNull(format.getString(MediaFormat.KEY_MIME))
            require(mime in codecs) { "Неподдерживаемый кодек: $mime. Используйте PCM16 WAV." }
            require(extractor.drmInitData == null) { "Защищённое аудио не поддерживается" }
            if (format.containsKey(MediaFormat.KEY_DURATION)) {
                require(format.getLong(MediaFormat.KEY_DURATION) <= PcmWav.MAX_SECONDS * 1_000_000L) {
                    "Максимум 120 секунд"
                }
            }
            fun properties(value: MediaFormat): Pair<Int, Int> {
                val rate = value.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                val channels = value.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                require(rate in 8000..48000 && channels in 1..2) { "Нужны 8–48 кГц и 1–2 канала" }
                require(!value.containsKey(MediaFormat.KEY_PCM_ENCODING) ||
                    value.getInteger(MediaFormat.KEY_PCM_ENCODING) == AudioFormat.ENCODING_PCM_16BIT) {
                    "Декодер должен вернуть PCM16"
                }
                return rate to channels
            }
            properties(format)
            format.setInteger(MediaFormat.KEY_PCM_ENCODING, AudioFormat.ENCODING_PCM_16BIT)
            extractor.selectTrack(track)
            val codec = MediaCodec.createDecoderByType(mime)
            decoder = codec
            codec.configure(format, null, null, 0)
            codec.start()
            var inputDone = false
            var outputDone = false
            var timeline: DecodedPcmTimeline? = null
            val info = MediaCodec.BufferInfo()
            val deadline = SystemClock.elapsedRealtime() + 60_000
            fun check() {
                checkCancelled()
                require(SystemClock.elapsedRealtime() < deadline) { "Превышено время декодирования аудио" }
            }
            while (!outputDone) {
                check()
                if (!inputDone) {
                    val index = codec.dequeueInputBuffer(10_000)
                    if (index >= 0) {
                        val buffer = requireNotNull(codec.getInputBuffer(index))
                        buffer.clear()
                        require(extractor.sampleFlags and (MediaExtractor.SAMPLE_FLAG_ENCRYPTED or
                            MediaExtractor.SAMPLE_FLAG_PARTIAL_FRAME) == 0) { "Защищённый/неполный аудиокадр" }
                        val count = extractor.readSampleData(buffer, 0)
                        if (count < 0) {
                            codec.queueInputBuffer(index, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputDone = true
                        } else {
                            require(count > 0 && count <= buffer.capacity()) { "Некорректный аудиокадр" }
                            codec.queueInputBuffer(index, 0, count, extractor.sampleTime, 0)
                            extractor.advance()
                        }
                    }
                }
                val index = codec.dequeueOutputBuffer(info, 10_000)
                if (index == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    val (rate, channels) = properties(codec.outputFormat)
                    writer?.let { require(it.sampleRate == rate && it.channels == channels) { "Формат меняется внутри записи" } }
                } else if (index >= 0) {
                    try {
                        if (info.size > 0 && info.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG == 0) {
                            val (rate, channels) = properties(codec.outputFormat)
                            val sink = writer ?: Pcm16WavWriter(destination, rate, channels).also { writer = it }
                            require(sink.sampleRate == rate && sink.channels == channels) { "Формат меняется внутри записи" }
                            val clock = timeline ?: DecodedPcmTimeline(rate, channels).also { timeline = it }
                            clock.accept(info.size, info.presentationTimeUs)
                            val pcm = requireNotNull(codec.getOutputBuffer(index)).duplicate()
                            require(info.offset >= 0 && info.size <= pcm.capacity() - info.offset)
                            pcm.limit(info.offset + info.size); pcm.position(info.offset)
                            sink.append(pcm, ::check)
                        }
                        outputDone = info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0
                    } finally { codec.releaseOutputBuffer(index, false) }
                }
            }
            check()
            val duration = requireNotNull(writer) { "Декодер не вернул аудио" }.finish()
            // Same validated PCM path used by recorded/WAV input and ASR.
            destination.inputStream().use { PcmWav.read(it, checkCancelled) }
            checkCancelled()
            accepted = true
            return AudioSnapshot(destination, duration)
        } finally {
            try { writer?.close() }
            finally {
                try { decoder?.release() }
                finally { extractor.release(); if (!accepted) destination.delete() }
            }
        }
    }
}
