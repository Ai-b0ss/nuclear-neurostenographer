package ru.neurostenographer.core

fun testDiarizationTimeEstimate() {
    val initial = DiarizationTimeEstimate.begin(1_000, 120_000)
    check(initial.provisional())
    check(initial.remainingMs(1_000) == 40_000L)
    check(initial.elapsedMs(6_000) == 5_000L)
    check(initial.remainingMs(6_000) == 35_000L)
    val calibrated = DiarizationTimeEstimate.begin(1_000, 120_000, 0.5)
    check(calibrated.historyCalibrated && calibrated.initialTotalWallMs == 64_000L)
    check(!DiarizationTimeEstimate.begin(1_000, 120_000, Double.NaN).historyCalibrated)
    check(!DiarizationTimeEstimate.begin(1_000, 120_000, -0.4).historyCalibrated)
    val advanced = initial.withProgress(1, 12).withProgress(6, 12)
    check(!advanced.provisional())
    check(advanced.totalChunks == 12 && advanced.completedChunks == 6)
    check(advanced.remainingMs(21_000) != null)
    check(advanced.withProgress(5,12) == advanced)
    check(advanced.withProgress(6,11) == advanced)
    check(advanced.withProgress(13,12) == advanced)
    check(advanced.withProgress(12,12).remainingMs(100_000) == null)
    check(initial.remainingMs(100_000) == null)
    check(initial.elapsedMs(0) == 0L)
    println("PASS diarization ETA startup, real chunk updates, timeout and guards")
}
