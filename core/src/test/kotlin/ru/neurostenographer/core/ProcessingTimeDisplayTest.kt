package ru.neurostenographer.core

fun testProcessingTimeDisplay() {
    val f = ProcessingTimeDisplay::approximateRemainingMs
    check(f(null) == null)
    check(f(0L) == null)
    check(f(-12_000L) == null)
    check(f(1L) == 5_000L)
    check(f(2_499L) == 5_000L)
    check(f(5_000L) == 5_000L)
    check(f(12_500L) == 15_000L)
    check(f(29_900L) == 30_000L)
    check(f(61_000L) == 60_000L)
    // Once a native worker ends, ViewModel must switch stages rather than
    // continue showing the no-longer-present diarization ETA.
    println("PASS processing ETA single rounded value, unknown, expired and active-zero guard")
}
