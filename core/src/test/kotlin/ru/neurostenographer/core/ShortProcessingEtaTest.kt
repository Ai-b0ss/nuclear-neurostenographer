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
    check(afterC2.remainingRangeWallMs(11_000L)!!.let { it.second > it.first })
    // Regression: irregular ASR window durations may not jerk the predicted
    // final deadline backward and forward by 10–20 seconds at each callback.
    var stepped = afterC2
    for ((fraction, time) in listOf(0.49 to 12_000L, 0.54 to 17_000L,
        0.59 to 25_000L, 0.68 to 27_000L, 0.74 to 36_000L)) {
        val previous = stepped.estimatedTotalWallMs
        val last = stepped.lastCheckpointMs ?: stepped.startedAtMs
        stepped = stepped.checkpoint(fraction, time)
        check(kotlin.math.abs(stepped.estimatedTotalWallMs - previous) <=
            maxOf(2_000L, (time - last) / 5L) ||
            stepped.estimatedTotalWallMs == time - stepped.startedAtMs + 1000L)
        val range = stepped.remainingRangeWallMs(time)
        if (range != null) check(range.first >= 5_000 && range.second > range.first)
    }
    check(runCatching { ShortProcessingEta(0L, Double.NaN) }.isFailure)
    println("PASS short recognition ETA measured checkpoints")
}
