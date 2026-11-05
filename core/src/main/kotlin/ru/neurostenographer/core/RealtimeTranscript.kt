package ru.neurostenographer.core

/** C2 commits past acoustic frames once. Freeze completed phrase attribution after
 * a 650-ms frontier margin, so an hour's text is not re-fused against all past turns.
 * Only the newest phrase is shown as unknown at its initial ASR notification. */
class RealtimeTranscript {
    private class Entry(val span: SampleSpan, var words: List<RecognizedWord>, var chunk: RecognizedChunk?,
                        var stable: List<TranscriptSegment>? = null)
    private val entries = mutableListOf<Entry>()
    val pendingWords get() = entries.sumOf { it.words.size }
    val stableEntries get() = entries.count { it.stable != null }

    fun add(span: SampleSpan, words: List<RecognizedWord>, chunk: RecognizedChunk?) {
        require(entries.lastOrNull()?.span?.end?.let { it <= span.start } != false)
        require(words.all { it.startMs >= span.startMs && it.endMs <= span.endMs })
        entries += Entry(span, words.toList(), chunk)
    }

    fun snapshot(turns: List<SpeakerTurn>, committedMs: Long, initialUnknown: Boolean = false): List<TranscriptSegment> {
        val result = entries.flatMapIndexed { index, entry ->
            entry.stable?.let { return@flatMapIndexed it }
            val unknown = initialUnknown && index == entries.lastIndex
            val relevant = if (unknown) emptyList() else turns.filter { it.endMs > entry.span.startMs && it.startMs < entry.span.endMs }
            val ready = if (unknown) emptyList() else entry.words.filter { it.endMs <= committedMs }
            val pending = entry.words.filter { unknown || it.endMs > committedMs }
            val segments = (TranscriptFusion.attributeWords(ready, relevant) +
                TranscriptFusion.attributeWords(pending, emptyList()) +
                TranscriptFusion.attributeChunks(listOfNotNull(entry.chunk),
                    if (unknown || entry.span.endMs > committedMs) emptyList() else relevant)).sortedBy { it.startMs }
            if (!unknown && entry.span.endMs + 650 <= committedMs) {
                entry.stable = segments; entry.words = emptyList(); entry.chunk = null
            }
            segments
        }
        return TranscriptFusion.mergeReplies(result)
    }
}
