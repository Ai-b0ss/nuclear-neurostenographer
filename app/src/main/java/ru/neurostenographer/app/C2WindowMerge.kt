package ru.neurostenographer.app

import ru.neurostenographer.core.AudioWindow
import ru.neurostenographer.core.SpeakerTurn

/** Join close ASR windows only when the complete span has one eligible C2 speaker. */
object C2WindowMerge {
    const val MAX_GAP_MS = 400L

    private fun uniqueCoveredSpeaker(window: AudioWindow, turns: List<SpeakerTurn>): String? {
        val overlapping = turns.filter { it.startMs < window.endMs && it.endMs > window.startMs }
        if (overlapping.isEmpty() || overlapping.any { !it.attributionEligible }) return null
        val speakers = overlapping.map { it.speakerId }.distinct()
        if (speakers.size != 1) return null
        val clipped = overlapping.map { maxOf(window.startMs, it.startMs) to minOf(window.endMs, it.endMs) }
            .sortedBy { it.first }
        var covered = 0L
        var end = window.startMs
        for ((start, stop) in clipped) {
            covered += (stop - maxOf(start, end)).coerceAtLeast(0)
            end = maxOf(end, stop)
        }
        return speakers.single().takeIf { covered * 10 >= (window.endMs - window.startMs) * 9 }
    }

    fun apply(windows: List<AudioWindow>, turns: List<SpeakerTurn>,
              maxGapMs: Long = MAX_GAP_MS): List<AudioWindow> {
        require(maxGapMs in 0..1000)
        val out = mutableListOf<AudioWindow>()
        for (window in windows) {
            val previous = out.lastOrNull()
            val merged = if (previous == null) null else AudioWindow(previous.startMs, window.endMs)
            val speaker = previous?.let { uniqueCoveredSpeaker(it, turns) }
            if (previous != null && merged != null && window.startMs - previous.endMs in 0..maxGapMs &&
                merged.endMs - merged.startMs <= 20_000 && speaker != null &&
                speaker == uniqueCoveredSpeaker(window, turns) &&
                speaker == uniqueCoveredSpeaker(merged, turns)) {
                out[out.lastIndex] = merged
            } else out += window
        }
        return out
    }
}
