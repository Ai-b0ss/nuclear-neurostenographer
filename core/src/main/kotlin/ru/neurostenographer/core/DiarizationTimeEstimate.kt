package ru.neurostenographer.core

import kotlin.math.roundToLong

/**
 * Monotonic, explicitly approximate timing for Nemotron/C0. Native C2 sends
 * a completed-chunk count for BOTH inference passes, not decoded audio time.
 * The initial forecast is a conservative device heuristic until real C2
 * progress or a previously measured per-device rate is available.
 */
data class DiarizationTimeEstimate(
    val startedAtMs: Long,
    val audioDurationMs: Long,
    val initialTotalWallMs: Long,
    val historyCalibrated: Boolean = false,
    val completedChunks: Int = 0,
    val totalChunks: Int = 0
) {
    init {
        require(startedAtMs >= 0 && audioDurationMs > 0 && initialTotalWallMs > 0)
        require(completedChunks >= 0 && totalChunks >= 0)
        require(totalChunks == 0 || completedChunks <= totalChunks)
    }

    fun elapsedMs(nowMs: Long): Long = (nowMs - startedAtMs).coerceAtLeast(0)

    fun withProgress(completed: Int, total: Int): DiarizationTimeEstimate {
        if (total <= 0 || completed !in 0..total || (totalChunks > 0 &&
                (total != totalChunks || completed < completedChunks))) return this
        return copy(completedChunks = completed, totalChunks = total)
    }

    fun remainingMs(nowMs: Long): Long? {
        if (totalChunks > 0 && completedChunks >= totalChunks) return null
        val elapsed = elapsedMs(nowMs)
        // The first native chunk includes model startup and is not a reliable
        // steady-state throughput sample. Blend estimates until enough chunks.
        val estimate = if (completedChunks == 0 || totalChunks == 0) initialTotalWallMs
        else {
            val measured = elapsed.toDouble() * totalChunks / completedChunks
            val weight = when {
                completedChunks <= 1 -> 0.25
                completedChunks * 4 < totalChunks -> 0.55
                else -> 0.85
            }
            (initialTotalWallMs * (1.0 - weight) + measured * weight)
                .coerceIn(1_000.0, 8 * 60 * 60 * 1000.0).roundToLong()
        }
        // A late native stage may exceed a forecast: never claim that work is
        // finished or display an invented 00:00 countdown while still active.
        return (estimate - elapsed).takeIf { it > 0 }
    }

    fun provisional(): Boolean = totalChunks == 0 || completedChunks == 0

    companion object {
        fun begin(startedAtMs: Long, audioMs: Long, measuredRatio: Double? = null): DiarizationTimeEstimate {
            require(audioMs > 0 && startedAtMs >= 0)
            val valid = measuredRatio?.takeIf { it.isFinite() && it in 0.04..5.0 }
            val guess = (4_000.0 + audioMs * (valid ?: 0.3))
                .coerceIn(5_000.0, 60 * 60 * 1000.0).roundToLong()
            return DiarizationTimeEstimate(startedAtMs, audioMs, guess, historyCalibrated = valid != null)
        }
    }
}
