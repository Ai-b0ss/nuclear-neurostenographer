package ru.neurostenographer.core

import java.util.concurrent.atomic.AtomicLong

data class SampleSpan(val start: Long, val end: Long, val readyAt: Long) {
    init { require(start >= 0 && end > start && readyAt >= end) }
    val startMs get() = start / 16
    val endMs get() = end / 16
}

/** One writer, one reader. Reader never holds a capture lock; a race returns null
 * and is recovered from the durable WAV. Overwrite is observable, never silent loss. */
class RealtimeRing(val capacity: Int = 60 * 16000) {
    private val samples = ShortArray(capacity)
    private val version = AtomicLong(0)
    private val committed = AtomicLong(0)
    val end get() = committed.get()
    init { require(capacity > 0) }
    fun append(input: ShortArray, count: Int = input.size) {
        require(count in 0..input.size && count <= capacity)
        val start = committed.get()
        version.incrementAndGet()
        for (i in 0 until count) samples[((start + i) % capacity).toInt()] = input[i]
        committed.set(start + count)
        version.incrementAndGet()
    }
    fun read(start: Long, count: Int): FloatArray? {
        require(start >= 0 && count >= 0)
        val before = version.get()
        if (before % 2L != 0L) return null
        val at = committed.get()
        if (start < at - capacity || start + count > at) return null
        val out = FloatArray(count) { samples[((start + it) % capacity).toInt()] / 32768f }
        return if (version.get() == before) out else null
    }
}

/** VAD decisions at 512 samples. Only completed phrases are queued; no partial decoding.
 * Windows may omit silence but cannot overlap or exceed the shared phrase limit. */
class RealtimePhrases(val silenceMs: Int = 500, val maxPhraseMs: Int = 15000) {
    private var cursor = 0L
    private var start = -1L
    private var lastSpeech = 0L
    private var speechSamples = 0L
    private var lastEnd = 0L
    init { require(silenceMs in listOf(300, 500) && maxPhraseMs in 10000..15000) }
    val consumed get() = cursor

    fun accept(count: Int, speech: Boolean, quietCut: (Long, Int) -> Int): List<SampleSpan> {
        require(count in 1..512)
        if (speech && start < 0) {
            start = maxOf(lastEnd, cursor - 3200, 0)
            speechSamples = 0
        }
        cursor += count
        if (speech) { lastSpeech = cursor; speechSamples += count }
        if (start < 0) return emptyList()
        if (!speech && cursor - lastSpeech >= silenceMs * 16) {
            val end = minOf(cursor, lastSpeech + 3200)
            val span = if (speechSamples >= 1600) SampleSpan(start, end, cursor) else null
            lastEnd = end; start = -1; speechSamples = 0
            return listOfNotNull(span)
        }
        val limit = maxPhraseMs * 16
        if (cursor - start >= limit) {
            val cut = start + quietCut(start, limit).coerceIn(limit - 32000, limit)
            val span = SampleSpan(start, cut, cursor)
            start = cut; lastEnd = cut; speechSamples = maxOf(0, lastSpeech - cut)
            return listOf(span)
        }
        return emptyList()
    }
    fun finish(): List<SampleSpan> {
        val span = if (start >= 0 && cursor > start && speechSamples >= 1600) SampleSpan(start, cursor, cursor) else null
        start = -1
        return listOfNotNull(span)
    }
}

/** Metadata-only queue, bounded independently from capture. Caller drains ASR before C2. */
class RealtimeQueue(private val capacity: Int = 3) {
    private val pending = ArrayDeque<SampleSpan>()
    var fallback = false
        private set
    var peak = 0
        private set
    val size get() = pending.size
    fun add(span: SampleSpan) {
        check(pending.size < capacity) { "Drain ASR before advancing VAD" }
        pending.addLast(span); peak = maxOf(peak, pending.size)
    }
    fun next(): SampleSpan? = if (pending.isEmpty()) null else pending.removeFirst()
    fun adapt(lagSamples: Long, thermalStatus: Int = 0): Boolean {
        if (pending.size >= 3 || lagSamples > 5 * 16000 || thermalStatus >= 2) fallback = true
        // Hysteresis: stay in the safe mode for the rest of this session.
        return fallback
    }
    fun clear() { pending.clear() }
}
