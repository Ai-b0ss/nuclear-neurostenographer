package ru.neurostenographer.core

/**
 * UI-only estimated audio playhead. The processing code confirms complete blocks;
 * intermediate seconds are approximated from measured throughput. The clock can
 * never report an unfinished block as completed.
 */
data class AudioProcessingClock(
    val totalMs: Long,
    val confirmedMs: Long,
    val activeEndMs: Long,
    val anchoredAtMs: Long,
    val audioPerWallMs: Double = 2.0,
    val calibrated: Boolean = false
) {
    init {
        require(totalMs > 0 && confirmedMs in 0..totalMs && activeEndMs in confirmedMs..totalMs)
        require(audioPerWallMs.isFinite() && audioPerWallMs > 0)
    }

    fun positionAt(nowMs: Long): Long {
        if (confirmedMs == totalMs) return totalMs
        val elapsed = (nowMs - anchoredAtMs).coerceAtLeast(0).toDouble()
        val advance = (elapsed * audioPerWallMs).coerceIn(0.0, totalMs.toDouble()).toLong()
        val upper = (activeEndMs - 1000L).coerceAtLeast(confirmedMs)
        return (confirmedMs + advance).coerceAtMost(upper).coerceAtMost(totalMs)
    }

    fun fractionAt(nowMs: Long): Float =
        (positionAt(nowMs).toDouble() / totalMs).coerceIn(0.0, 1.0).toFloat()

    fun remainingWallMs(nowMs: Long): Long =
        ((totalMs - positionAt(nowMs)).toDouble() / audioPerWallMs)
            .coerceIn(0.0, Long.MAX_VALUE.toDouble()).toLong()

    fun waitingForCheckpoint(nowMs: Long): Boolean =
        confirmedMs < activeEndMs && positionAt(nowMs) >=
            (activeEndMs - 1000L).coerceAtLeast(confirmedMs)

    /** Call after a complete block. Pure digital silence must not calibrate the rate. */
    fun advance(
        completedMs: Long, nextEndMs: Long, nowMs: Long,
        measuredWallMs: Long? = null
    ): AudioProcessingClock {
        require(completedMs in confirmedMs..totalMs && nextEndMs in completedMs..totalMs)
        val measured = measuredWallMs?.takeIf { it > 0 && completedMs > confirmedMs }?.let {
            ((completedMs - confirmedMs).toDouble() / it).coerceIn(0.05, 30.0)
        }
        val pace = when {
            measured == null -> audioPerWallMs
            !calibrated -> measured
            else -> audioPerWallMs * 0.55 + measured * 0.45
        }
        return copy(
            confirmedMs = completedMs, activeEndMs = nextEndMs,
            anchoredAtMs = nowMs, audioPerWallMs = pace,
            calibrated = calibrated || measured != null
        )
    }
}
