package ru.neurostenographer.core

/** ASR evidence is immutable; attribution is a replaceable view. Never discard word
 * boundaries when a phrase leaves the acoustic frontier: finalization can split it again.
 * PCM remains on disk; only text/times and the last per-phrase view are retained. */
class RealtimeTranscript {
    private class Entry(val span: SampleSpan, val words: List<RecognizedWord>, val chunk: RecognizedChunk?,
        var key: List<SpeakerTurn>? = null, var ready: Long = -1,
        var cached: List<TranscriptSegment> = emptyList())
    private val entries = mutableListOf<Entry>()
    val pendingWords get() = entries.sumOf { it.words.size }
    val stableEntries get() = 0 // live attribution is explicitly provisional

    fun add(span: SampleSpan, words: List<RecognizedWord>, chunk: RecognizedChunk?) {
        require(entries.lastOrNull()?.span?.end?.let { it <= span.start } != false)
        require(words.all { it.startMs >= span.startMs && it.endMs <= span.endMs })
        require(chunk == null || (chunk.startMs >= span.startMs && chunk.endMs <= span.endMs))
        entries += Entry(span, words.toList(), chunk)
    }

    fun snapshot(turns: List<SpeakerTurn>, committedMs: Long, initialUnknown: Boolean = false): List<TranscriptSegment> {
        // Sweep sorted non-overlapping ASR windows once. Avoid hour-long O(entries * turns)
        // rescans while retaining long speaker intervals that cross many phrase windows.
        val ordered = turns.sortedBy { it.startMs }
        val active = mutableListOf<SpeakerTurn>()
        var next = 0
        val result = entries.flatMapIndexed { index, entry ->
            val unknown = initialUnknown && index == entries.lastIndex
            active.removeAll { it.endMs <= entry.span.startMs }
            while (next < ordered.size && ordered[next].startMs < entry.span.endMs) {
                val turn = ordered[next++]
                if (turn.endMs > entry.span.startMs) active += turn
            }
            val relevant = if (unknown) emptyList() else active.toList()
            val frontier = if (unknown) -1 else minOf(committedMs, entry.span.endMs)
            if (entry.key != relevant || entry.ready != frontier) {
                val ready = entry.words.filter { it.endMs <= frontier }
                val pending = entry.words.filter { it.endMs > frontier }
                entry.cached = (TranscriptFusion.attributeWords(ready, relevant) +
                    TranscriptFusion.attributeWords(pending, emptyList()) +
                    TranscriptFusion.attributeChunks(listOfNotNull(entry.chunk),
                        if (entry.span.endMs > frontier) emptyList() else relevant)).sortedBy { it.startMs }
                entry.key = relevant; entry.ready = frontier
            }
            entry.cached
        }
        return TranscriptFusion.mergeReplies(result)
    }
}
