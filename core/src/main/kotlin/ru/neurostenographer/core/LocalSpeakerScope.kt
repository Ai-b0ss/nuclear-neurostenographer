package ru.neurostenographer.core

/** IDs of independent long-recording chunks cannot imply global voice identity. */
object LocalSpeakerScope {
    fun shift(segment: TranscriptSegment, offsetMs: Long, blockIndex: Int,
              trustedLinks: Map<String, String> = emptyMap()): TranscriptSegment {
        require(offsetMs >= 0 && blockIndex >= 0)
        fun scoped(id: String): String = trustedLinks[id] ?: ("Block " + (blockIndex + 1) + " / " + id)
        return segment.copy(
            startMs = Math.addExact(segment.startMs, offsetMs),
            endMs = Math.addExact(segment.endMs, offsetMs),
            speakerId = segment.speakerId?.let(::scoped),
            overlapSpeakers = segment.overlapSpeakers.map(::scoped)
        )
    }
}
