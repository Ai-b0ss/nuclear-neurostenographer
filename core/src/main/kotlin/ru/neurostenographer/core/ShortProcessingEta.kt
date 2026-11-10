package ru.neurostenographer.core

import kotlin.math.roundToLong

/**
 * Stage-based ETA for ordinary (<20-minute) recognition.
 *
 * Fractions are approximate computational weights, NOT percentages of recognized words.
 * A numeric countdown is withheld until a completed stage supplies measured throughput.
 * Stalled steps invalidate the number instead of reporting a dishonest "0 seconds".
 * Android wall time comes from SystemClock.elapsedRealtime (monotonic).
 */
data class ShortProcessingEta(
    val startedAtMs: Long,
    val phaseFraction: Double = 0.0,
    val estimatedTotalWallMs: Long = 0L,
    val calibrated: Boolean = false,
    val estimatingNextPhase: Boolean = false,
    val lastCheckpointMs: Long? = null
) {
    init {
        require(phaseFraction in 0.0..1.0 && phaseFraction.isFinite())
        require(estimatedTotalWallMs >= 0L)
    }

    fun remainingWallMs(nowMs: Long): Long? {
        if (!calibrated || estimatingNextPhase) return null
        val elapsed = (nowMs - startedAtMs).coerceAtLeast(0L)
        // The last checkpoint has not yet completed the next native operation.
        if (elapsed >= estimatedTotalWallMs) return null
        return (estimatedTotalWallMs - elapsed).coerceAtLeast(1000L)
    }

    /** Communicate uncertainty instead of a fake second-accurate deadline. */
    fun remainingRangeWallMs(nowMs: Long): Pair<Long, Long>? {
        val remaining = remainingWallMs(nowMs) ?: return null
        val lower = (remaining * 0.72 - 3_000).roundToLong().coerceAtLeast(5_000L)
        val upper = (remaining * 1.35 + 5_000).roundToLong().coerceAtLeast(lower + 5_000L)
        fun floor5(v: Long) = maxOf(5_000L, v / 5_000L * 5_000L)
        fun ceil5(v: Long) = (v / 5_000L + if (v % 5_000L != 0L) 1L else 0L) * 5_000L
        return floor5(lower) to maxOf(floor5(lower) + 5_000L, ceil5(upper))
    }

    fun checkpoint(completedFraction: Double, nowMs: Long): ShortProcessingEta {
        require(completedFraction.isFinite() && completedFraction in phaseFraction..0.99)
        val elapsed = (nowMs - startedAtMs).coerceAtLeast(1L)
        val measuredTotal = (elapsed / completedFraction.coerceAtLeast(0.05))
            .coerceAtMost(8 * 60 * 60 * 1000.0)
            .roundToLong()
        // Checkpoint costs vary (VAD, model loading, language detection and
        // the last ASR window). Recomputing an extrapolation after every
        // window with 65% weight created violent +/-15s ETA jumps.
        // Smooth it, and move the predicted finish by at most 2 seconds per
        // checkpoint (or 20% of a long interval), while keeping the numeric
        // display explicitly approximate.
        val total = if (!calibrated || estimatedTotalWallMs == 0L) measuredTotal
            else {
                val smooth = (estimatedTotalWallMs * 0.8 + measuredTotal * 0.2).roundToLong()
                val elapsedSince = (nowMs - (lastCheckpointMs ?: startedAtMs)).coerceAtLeast(0L)
                val budget = maxOf(2_000L, elapsedSince / 5)
                estimatedTotalWallMs + (smooth - estimatedTotalWallMs).coerceIn(-budget, budget)
            }
        return copy(phaseFraction = completedFraction,
            estimatedTotalWallMs = maxOf(total, elapsed + 1000L),
            calibrated = true, estimatingNextPhase = false, lastCheckpointMs = nowMs)
    }

    fun invalidateUntilCheckpoint(): ShortProcessingEta =
        copy(estimatingNextPhase = true)
}
