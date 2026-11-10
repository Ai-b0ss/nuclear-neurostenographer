package ru.neurostenographer.core

import kotlin.math.max
import kotlin.math.roundToLong

/**
 * UI-only monotonic ETA for the two-pass offline diarizer.
 *
 * Native chunks are measured at completion in the isolated worker. A naive
 * elapsed * totalChunks / completedChunks estimate is UNSTABLE: startup,
 * model warm-up and second-pass chunks have different costs, especially for
 * short clips (2-4 chunks). Instead keep a deadline updated only at real
 * progress checkpoints and limit each correction. The UI shows a coarse
 * uncertainty range, not spurious second-accurate guesses.
 *
 * No progress event is ever invented; the completed count is native evidence.
 */
data class DiarizationTimeEstimate(
    val startedAtMs: Long,
    val audioDurationMs: Long,
    val initialTotalWallMs: Long,
    val historyCalibrated: Boolean = false,
    val completedChunks: Int = 0,
    val totalChunks: Int = 0,
    val lastCheckpointMs: Long? = null,
    val averageChunkWallMs: Double? = null,
    val expectedFinishAtMs: Long = startedAtMs + initialTotalWallMs
) {
    init {
        require(startedAtMs >= 0L && audioDurationMs > 0L && initialTotalWallMs > 0L)
        require(completedChunks >= 0 && totalChunks >= 0)
        require(totalChunks == 0 || completedChunks <= totalChunks)
        require(lastCheckpointMs == null || lastCheckpointMs >= startedAtMs)
        require(averageChunkWallMs == null ||
            (averageChunkWallMs.isFinite() && averageChunkWallMs > 0.0))
    }

    fun elapsedMs(nowMs: Long): Long = (nowMs - startedAtMs).coerceAtLeast(0L)

    /** Preserve Kotlin source compatibility for two-argument test callers. */
    fun withProgress(completed: Int, total: Int): DiarizationTimeEstimate =
        withProgress(completed, total, startedAtMs)

    fun withProgress(completed: Int, total: Int, nowMs: Long): DiarizationTimeEstimate {
        if (total !in 1..10000 || completed !in 0..total ||
            completed < completedChunks ||
            (totalChunks > 0 && total != totalChunks) || nowMs < startedAtMs ||
            (lastCheckpointMs != null && nowMs < lastCheckpointMs)) return this
        if (total == totalChunks && completed == completedChunks) return this
        if (completed == total) {
            // Native inference has completed. Any post-processing/cleanup
            // still belongs to the worker, but a fake 00:00 is prohibited.
            return copy(completedChunks = completed, totalChunks = total, lastCheckpointMs = nowMs)
        }

        val previousAt = lastCheckpointMs
        val deltaChunks = completed - completedChunks
        val elapsedSinceCheckpoint = if (previousAt != null) (nowMs - previousAt).coerceAtLeast(0L) else 0L
        val newSample = if (previousAt != null && deltaChunks > 0 && elapsedSinceCheckpoint > 0L)
            elapsedSinceCheckpoint.toDouble() / deltaChunks else null

        // Ignore the first completed chunk for throughput calibration: it may
        // include model loading. EMA suppresses a fast/slow individual chunk.
        val previousPace = averageChunkWallMs
        val pace = when {
            newSample == null -> previousPace
            previousPace == null -> newSample
            else -> previousPace * 0.7 + newSample * 0.3
        }
        val remainingChunks = total - completed
        val predictedFinish = if (pace == null) expectedFinishAtMs
            else (nowMs + pace * remainingChunks + 1500.0).roundToLong()

        // Real elapsed time must not make the *remaining* estimate jump by
        // 10-20 seconds whenever the second pass performs a slower chunk.
        // Bound deadline correction to <=2s per event (or 20% of the interval
        // for very long chunks). A failed prediction expires to "refining"
        // rather than lying with 00:00.
        val correctionBudget = max(2_000L, elapsedSinceCheckpoint / 5L)
        val diff = (predictedFinish - expectedFinishAtMs).coerceIn(-correctionBudget, correctionBudget)
        val adjusted = expectedFinishAtMs + diff
        return copy(completedChunks = completed, totalChunks = total,
            lastCheckpointMs = nowMs,
            averageChunkWallMs = pace,
            expectedFinishAtMs = adjusted)
    }

    /** Remaining time is allowed to be unknown; never show 00:00 for active work. */
    fun remainingMs(nowMs: Long): Long? {
        if (totalChunks > 0 && completedChunks >= totalChunks) return null
        val remainder = expectedFinishAtMs - nowMs
        if (remainder <= 0) return null
        // If native execution stalls, the previous ETA stops being meaningful.
        val last = lastCheckpointMs
        if (last != null && completedChunks < totalChunks &&
            nowMs - last > max(15_000L, ((averageChunkWallMs ?: 5_000.0) * 3).roundToLong()))
            return null
        return remainder
    }

    /** Inclusive, rounded 5-second wall-time band that admits uncertainty. */
    fun remainingRangeMs(nowMs: Long): Pair<Long, Long>? {
        val remaining = remainingMs(nowMs) ?: return null
        val uncertainty = if (historyCalibrated && completedChunks >= 2) 0.25 else 0.40
        val lower = (remaining * (1.0 - uncertainty) - 3_000.0)
            .roundToLong().coerceAtLeast(5_000L)
        val upper = (remaining * (1.0 + uncertainty) + 5_000.0)
            .roundToLong().coerceAtLeast(lower + 5_000L)
        fun floor5(value: Long): Long = max(5_000L, value / 5_000L * 5_000L)
        fun ceil5(value: Long): Long = (value / 5_000L + if (value % 5_000L > 0) 1L else 0L) * 5_000L
        return floor5(lower) to max(floor5(lower) + 5_000L, ceil5(upper))
    }

    /** Until two native chunks (not a guess), the band is explicitly provisional. */
    fun provisional(): Boolean = !historyCalibrated || completedChunks < 2 || totalChunks == 0

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
