package ru.neurostenographer.core

import kotlin.math.max
import kotlin.math.min

/** All intervals are milliseconds from the beginning of the same recording. */
data class SpeakerTurn(val startMs: Long, val endMs: Long, val speakerId: String) {
    init { require(startMs >= 0 && endMs > startMs && speakerId.isNotBlank()) }
}
data class RecognizedWord(val startMs: Long, val endMs: Long, val text: String) {
    init { require(startMs >= 0 && endMs > startMs && text.isNotBlank()) }
}
data class RecognizedChunk(val startMs: Long, val endMs: Long, val text: String) {
    init { require(startMs >= 0 && endMs > startMs && text.isNotBlank()) }
}
data class TranscriptSegment(
    val startMs: Long,
    val endMs: Long,
    val speakerId: String?,
    val text: String,
    val overlappingSpeech: Boolean = false,
    val attributionReliable: Boolean = false
) {
    init { require(startMs >= 0 && endMs > startMs && text.isNotBlank()) }
}

/** Does not invent speaker IDs or word timestamps when evidence is ambiguous. */
object TranscriptFusion {
    private data class Attribution(val speakerId: String?, val overlap: Boolean, val reliable: Boolean)

    fun attributeWords(
        words: List<RecognizedWord>,
        turns: List<SpeakerTurn>,
        minDominance: Double = 0.55,
        minMargin: Double = 0.25,
        maxGapMs: Long = 650
    ): List<TranscriptSegment> {
        require(minDominance in 0.0..1.0 && minMargin in 0.0..1.0 && maxGapMs >= 0)
        val input = words.sortedWith(compareBy<RecognizedWord> { it.startMs }.thenBy { it.endMs })
        val result = mutableListOf<TranscriptSegment>()
        for (word in input) {
            val a = attribute(word.startMs, word.endMs, turns, minDominance, minMargin)
            val current = TranscriptSegment(word.startMs, word.endMs, a.speakerId, word.text, a.overlap, a.reliable)
            val previous = result.lastOrNull()
            if (previous != null && previous.speakerId == current.speakerId &&
                previous.overlappingSpeech == current.overlappingSpeech &&
                previous.attributionReliable == current.attributionReliable &&
                current.startMs <= previous.endMs + maxGapMs) {
                val noSpace = current.text.first() in ".,!?;:…»)" || previous.text.last() in "(«"
                result[result.lastIndex] = previous.copy(
                    endMs = max(previous.endMs, current.endMs),
                    text = previous.text + (if (noSpace) "" else " ") + current.text
                )
            } else result.add(current)
        }
        return result
    }

    /** Conservative fallback for ASR without word-level timestamps. */
    fun attributeChunks(chunks: List<RecognizedChunk>, turns: List<SpeakerTurn>): List<TranscriptSegment> =
        chunks.sortedBy { it.startMs }.map { c ->
            val a = attribute(c.startMs, c.endMs, turns, 0.9, 0.8)
            TranscriptSegment(c.startMs, c.endMs, a.speakerId, c.text, a.overlap, a.reliable)
        }

    private fun normalize(spans: List<Pair<Long, Long>>): List<Pair<Long, Long>> {
        val ordered = spans.sortedBy { it.first }
        val output = mutableListOf<Pair<Long, Long>>()
        for ((s, e) in ordered) {
            val previous = output.lastOrNull()
            if (previous != null && s <= previous.second)
                output[output.lastIndex] = previous.first to max(previous.second, e)
            else output.add(s to e)
        }
        return output
    }

    private fun total(spans: List<Pair<Long, Long>>): Long =
        normalize(spans).sumOf { it.second - it.first }

    private fun intersection(a: List<Pair<Long, Long>>, b: List<Pair<Long, Long>>): Long {
        var sum = 0L
        val aa = normalize(a)
        val bb = normalize(b)
        var i = 0
        var j = 0
        while (i < aa.size && j < bb.size) {
            sum += max(0L, min(aa[i].second, bb[j].second) - max(aa[i].first, bb[j].first))
            if (aa[i].second < bb[j].second) i++ else j++
        }
        return sum
    }

    private fun attribute(
        start: Long, end: Long, turns: List<SpeakerTurn>,
        minDominance: Double, minMargin: Double
    ): Attribution {
        val clips = turns.mapNotNull { turn ->
            val s = max(start, turn.startMs)
            val e = min(end, turn.endMs)
            if (e > s) turn.speakerId to (s to e) else null
        }
        if (clips.isEmpty()) return Attribution(null, false, false)
        val grouped = clips.groupBy({ it.first }, { it.second })
        val ranked = grouped.mapValues { total(it.value) }
            .toList().sortedWith(compareByDescending<Pair<String, Long>> { it.second }.thenBy { it.first })
        val groups = grouped.keys.toList()
        val overlap = groups.indices.any { i ->
            ((i + 1) until groups.size).any { j ->
                intersection(grouped.getValue(groups[i]), grouped.getValue(groups[j])) > 0L
            }
        }
        val duration = (end - start).toDouble()
        val second = ranked.getOrNull(1)?.second ?: 0L
        val reliable = !overlap && ranked[0].second / duration >= minDominance &&
            (ranked[0].second - second) / duration >= minMargin
        return Attribution(if (reliable) ranked[0].first else null, overlap, reliable)
    }
}

object TranscriptExport {
    private fun human(ms: Long): String =
        "%02d:%02d".format(ms / 60000, (ms / 1000) % 60)
    private fun srtTime(ms: Long): String =
        "%02d:%02d:%02d,%03d".format(ms / 3600000, (ms / 60000) % 60, (ms / 1000) % 60, ms % 1000)
    private fun jsonString(s: String): String = buildString {
        append('"')
        for (c in s) when (c) {
            '"' -> append("\\\"")
            '\\' -> append("\\\\")
            '\n' -> append("\\n")
            '\r' -> append("\\r")
            '\t' -> append("\\t")
            else -> if (c.code < 32) append("\\u%04x".format(c.code)) else append(c)
        }
        append('"')
    }
    fun txt(items: List<TranscriptSegment>): String = items.joinToString("\n") {
        "[" + human(it.startMs) + "–" + human(it.endMs) + "] " +
            (it.speakerId ?: "Не определён") + ": " + it.text +
            (if (it.overlappingSpeech) " [перекрытие речи]" else "")
    }
    fun srt(items: List<TranscriptSegment>): String =
        items.sortedBy { it.startMs }.mapIndexed { i, s ->
            (i + 1).toString() + "\n" + srtTime(s.startMs) + " --> " +
                srtTime(s.endMs) + "\n" + (s.speakerId ?: "Не определён") + ": " + s.text
        }.joinToString("\n\n")
    fun json(items: List<TranscriptSegment>): String =
        "{\n  \"version\": 1,\n  \"units\": \"milliseconds\",\n  \"segments\": [\n" +
            items.joinToString(",\n") {
                "    {\"start_ms\": " + it.startMs + ", \"end_ms\": " + it.endMs +
                    ", \"speaker_id\": " + (it.speakerId?.let(::jsonString) ?: "null") +
                    ", \"text\": " + jsonString(it.text) + ", \"overlapping_speech\": " +
                    it.overlappingSpeech + ", \"attribution_reliable\": " + it.attributionReliable + "}"
            } + "\n  ]\n}\n"
}
