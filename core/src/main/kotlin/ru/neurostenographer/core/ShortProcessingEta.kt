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
    val estimatingNextPhase: Boolean = false
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

    fun checkpoint(completedFraction: Double, nowMs: Long): ShortProcessingEta {
        require(completedFraction.isFinite() && completedFraction in phaseFraction..0.99)
        val elapsed = (nowMs - startedAtMs).coerceAtLeast(1L)
        val measuredTotal = (elapsed / completedFraction.coerceAtLeast(0.05))
            .coerceAtMost(8 * 60 * 60 * 1000.0)
            .roundToLong()
        val total = if (!calibrated || estimatedTotalWallMs == 0L) measuredTotal
            else (estimatedTotalWallMs * 0.35 + measuredTotal * 0.65).roundToLong()
        return copy(phaseFraction = completedFraction,
            estimatedTotalWallMs = maxOf(total, elapsed + 1000L),
            calibrated = true, estimatingNextPhase = false)
    }

    fun invalidateUntilCheckpoint(): ShortProcessingEta =
        copy(estimatingNextPhase = true)
}
