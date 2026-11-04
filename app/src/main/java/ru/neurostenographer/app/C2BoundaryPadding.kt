package ru.neurostenographer.app

import ru.neurostenographer.core.DiarizationTimeline

/** Extend C2 activity boundaries without another neural inference pass. */
object C2BoundaryPadding {
    const val PADDING_MS = 150L

    fun apply(output: DiarizationOutput, audioMs: Long, paddingMs: Long = PADDING_MS): DiarizationOutput {
        require(audioMs > 0 && paddingMs in 0..500)
        if (paddingMs == 0L) return output
        val turns = output.turns.map { turn ->
            turn.copy(startMs = (turn.startMs - paddingMs).coerceAtLeast(0),
                endMs = (turn.endMs + paddingMs).coerceAtMost(audioMs))
        }
        val windows = DiarizationTimeline.windows(turns, audioMs).filter { window ->
            turns.any { it.startMs <= window.startMs && it.endMs >= window.endMs }
        }
        return output.copy(turns = turns, windows = windows)
    }
}
