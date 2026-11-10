package ru.neurostenographer.core

import kotlin.math.max
import kotlin.math.roundToLong

/**
 * Stage-specific wall-clock ETA for offline ASR.
 *
 * Diarization and recognition have very different CPU costs. Therefore
 * speaker-diarization elapsed time must NOT be extrapolated as an estimate
 * for the text-recognition stage. The forecast starts after actual word
 * decoding-window completion callbacks, and disappears during finalization.
 */
data class AsrWindowEta(
    val startedAtMs: Long,
    val totalWindows: Int,
    val completedWindows: Int,
    val lastCheckpointAtMs: Long = startedAtMs,
    val observedMsPerWindow: Double? = null,
    val expectedFinishAtMs: Long? = null,
    val samples: Int = 0
) {
    init {
        require(startedAtMs >= 0)
        require(totalWindows in 1..10000 && completedWindows in 0..totalWindows)
        require(lastCheckpointAtMs >= startedAtMs)
        require(samples >= 0)
        require(observedMsPerWindow == null ||
            (observedMsPerWindow.isFinite() && observedMsPerWindow > 0))
    }

    fun checkpoint(completed: Int, total: Int, nowMs: Long): AsrWindowEta {
        if (total != totalWindows || completed !in 0..totalWindows ||
            completed <= completedWindows || nowMs < lastCheckpointAtMs)
            return this
        if (completed == totalWindows) {
            // Explicit completion: no countdown during optional overlap
            // postprocessing, saving or history finalization.
            return copy(completedWindows = completed, lastCheckpointAtMs = nowMs,
                expectedFinishAtMs = null)
        }
        val elapsed = nowMs - lastCheckpointAtMs
        val n = completed - completedWindows
        val sample = (elapsed.toDouble() / n).takeIf { it >= 1.0 }
        val old = observedMsPerWindow
        val smoothed = when {
            sample == null -> old
            old == null -> sample
            else -> old * 0.65 + sample * 0.35
        }
        val deadline = if (smoothed == null) null else {
            // Small tail reserve for assembling the transcript; not a
            // forecast of a separate optional FDDT model pass.
            val desired = nowMs + (totalWindows - completed) * smoothed + 3_000.0
            val previous = expectedFinishAtMs
            if (previous == null) desired.roundToLong()
            else {
                // Native windows can be variable lengths. Change a predicted
                // deadline gradually, never 10-20 s per completed window.
                val budget = max(2_000L, elapsed / 4L)
                previous + (desired.roundToLong() - previous).coerceIn(-budget,budget)
            }
        }
        return copy(completedWindows = completed,lastCheckpointAtMs = nowMs,
            observedMsPerWindow = smoothed,expectedFinishAtMs = deadline,
            samples = if (sample == null) samples else samples + 1)
    }

    fun remainingMs(nowMs: Long): Long? {
        if (completedWindows >= totalWindows || samples < 1) return null
        val deadline = expectedFinishAtMs ?: return null
        val remaining = deadline - nowMs
        if (remaining <= 0L) return null
        val pace = observedMsPerWindow ?: return null
        if (nowMs - lastCheckpointAtMs > max(20_000L,(pace * 3.0).roundToLong()))
            return null
        return remaining
    }

    companion object {
        fun begin(startedAtMs: Long, total: Int, firstCompleted: Int): AsrWindowEta =
            AsrWindowEta(startedAtMs,total,firstCompleted)
    }
}
