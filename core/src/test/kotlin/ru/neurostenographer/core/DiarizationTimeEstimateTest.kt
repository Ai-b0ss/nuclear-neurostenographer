package ru.neurostenographer.core

fun testDiarizationTimeEstimate() {
    val initial = DiarizationTimeEstimate.begin(1_000L, 120_000L)
    check(initial.provisional())
    check(initial.remainingMs(1_000L) == 40_000L)
    check(initial.elapsedMs(6_000L) == 5_000L)
    check(initial.remainingMs(6_000L) == 35_000L)
    check(initial.remainingRangeMs(6_000L)!!.let { it.first in 5_000L..it.second })
    val history = DiarizationTimeEstimate.begin(1_000L, 120_000L, 0.5)
    check(history.historyCalibrated && history.initialTotalWallMs == 64_000L)
    check(!DiarizationTimeEstimate.begin(1_000L, 120_000L, Double.NaN).historyCalibrated)
    check(!DiarizationTimeEstimate.begin(1_000L, 120_000L, -0.4).historyCalibrated)

    // Critical regression: 2/4 native chunks with variable costs used to
    // make the timer oscillate 16s -> 20s -> 9s -> 26s with fake precision.
    var estimate = DiarizationTimeEstimate.begin(1_000L, 45_000L, 0.42)
    val times = listOf(6_000L, 12_000L, 21_000L)
    var prevDeadline = estimate.expectedFinishAtMs
    for ((index, now) in times.withIndex()) {
        estimate = estimate.withProgress(index + 1, 4, now)
        val movement = estimate.expectedFinishAtMs - prevDeadline
        check(movement in -2_000L..2_000L) { "Unstable deadline correction: $movement" }
        check(estimate.remainingMs(now) != null)
        val range = estimate.remainingRangeMs(now)!!
        check(range.first % 5_000L == 0L && range.second % 5_000L == 0L)
        check(range.second > range.first)
        prevDeadline = estimate.expectedFinishAtMs
    }
    check(estimate.completedChunks == 3 && estimate.totalChunks == 4)
    check(estimate.withProgress(2, 4, 22_000L) == estimate)
    check(estimate.withProgress(3, 5, 22_000L) == estimate)
    check(estimate.withProgress(5, 4, 22_000L) == estimate)
    check(estimate.withProgress(4, 4, 24_000L).remainingMs(24_000L) == null)

    // Stalled native callbacks must not show "00:00" or an expired prediction.
    check(initial.remainingMs(100_000L) == null)
    check(initial.remainingRangeMs(100_000L) == null)
    check(initial.elapsedMs(0L) == 0L)
    check(estimate.remainingMs(100_000L) == null)
    // Even if callbacks arrive out of order, displayed chunks never regress.
    check(estimate.withProgress(1, 4, 23_000L) == estimate)
    check(estimate.withProgress(3, 4, 20_000L) == estimate)
    println("PASS diarization stable ETA bands, monotonic deadlines, chunk updates and stall guards")
}
