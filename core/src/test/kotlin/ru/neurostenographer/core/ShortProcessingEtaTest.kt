package ru.neurostenographer.core

fun testShortProcessingEta() {
    val initial = ShortProcessingEta(1000L)
    check(initial.remainingWallMs(2000L) == null)
    val afterC2 = initial.checkpoint(0.45, 10_000L)
    check(afterC2.calibrated)
    check(afterC2.remainingWallMs(11_000L)!! > 0)
    check(afterC2.remainingWallMs(afterC2.startedAtMs + afterC2.estimatedTotalWallMs + 1) == null)
    val paused = afterC2.invalidateUntilCheckpoint()
    check(paused.remainingWallMs(11_000L) == null)
    val updated = paused.checkpoint(0.76, 20_000L)
    check(updated.remainingWallMs(20_000L)!! > 0)
    check(updated.estimatedTotalWallMs > 19_000L)
    check(runCatching { updated.checkpoint(.5, 21_000L) }.isFailure)
    check(runCatching { ShortProcessingEta(0L, Double.NaN) }.isFailure)
    println("PASS short recognition ETA measured checkpoints")
}
