package ru.neurostenographer.core

fun testAsrWindowEta() {
    val first = AsrWindowEta.begin(1_000, 17, 1)
    check(first.remainingMs(1_000) == null)
    val second = first.checkpoint(2,17,4_000)
    check(second.samples == 1 && second.observedMsPerWindow == 3_000.0)
    check(second.remainingMs(4_000)!!.let { it in 40_000L..60_000L })
    val third = second.checkpoint(3,17,6_000)
    check(third.remainingMs(6_000) != null)
    check(third.expectedFinishAtMs!! - second.expectedFinishAtMs!! in -2_000L..2_000L)

    // Regression: just after the last actual decoding window, the old
    // total-stage timer still claimed ~20s, but result appeared in ~5s.
    val beforeLast = third.checkpoint(16,17,35_000)
    check(beforeLast.completedWindows == 16)
    val done = beforeLast.checkpoint(17,17,38_000)
    check(done.completedWindows == 17 && done.remainingMs(38_000) == null)
    check(done.expectedFinishAtMs == null)

    check(third.checkpoint(2,17,7_000) == third)
    check(third.checkpoint(3,18,7_000) == third)
    check(third.checkpoint(3,17,5_000) == third)
    check(third.remainingMs(100_000) == null)
    val one = AsrWindowEta.begin(1_000,1,1)
    check(one.remainingMs(1_000) == null)
    println("PASS ASR stage-specific ETA windows, deadline smoothing, finalizing and stale callbacks")
}
