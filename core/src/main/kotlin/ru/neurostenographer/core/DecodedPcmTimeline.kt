package ru.neurostenographer.core

/** Reject timestamp gaps rather than silently shortening/lengthening a recording.
 * Codec encoder-delay/padding treatment is platform-dependent. Origin is the first
 * decoded sample; tolerance is explicit, not word alignment or timestamp accuracy.
 */
class DecodedPcmTimeline(private val rate: Int, private val channels: Int) {
    private var origin: Long? = null
    private var frames = 0L
    init { require(rate in 8000..48000 && channels in 1..2) }

    fun accept(bytes: Int, timestampUs: Long) {
        require(bytes > 0 && bytes % (channels * 2) == 0) { "Обрезанный PCM16 кадр" }
        val next = frames + bytes / (channels * 2)
        require(next <= rate.toLong() * PcmWav.MAX_SECONDS) { "Максимум 120 секунд" }
        val start = origin ?: timestampUs
        val elapsed = Math.subtractExact(timestampUs, start)
        val delta = Math.subtractExact(elapsed, frames * 1_000_000 / rate)
        require(delta in -100_000L..100_000L) { "Разрыв временной шкалы аудио; преобразуйте файл в WAV" }
        origin = start
        frames = next
    }
}
