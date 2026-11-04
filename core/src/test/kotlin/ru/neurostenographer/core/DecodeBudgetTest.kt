package ru.neurostenographer.core

fun testDecodeBudget() {
    check(DecodeBudget.millis(5_000) == DecodeBudget.MIN_MS) { "short file keeps the 60 s floor" }
    check(DecodeBudget.millis(null) == DecodeBudget.UNKNOWN_DURATION_MS) { "unknown duration" }
    check(DecodeBudget.millis(0) == DecodeBudget.UNKNOWN_DURATION_MS) { "zero duration is not trusted" }
    check(DecodeBudget.millis(-1) == DecodeBudget.UNKNOWN_DURATION_MS) { "negative duration is not trusted" }
    check(DecodeBudget.millis(600_000) == 300_000L) { "10 minutes of audio gets 5 minutes" }
    check(DecodeBudget.millis(PcmWav.MAX_SECONDS * 1000L) == DecodeBudget.MAX_MS) { "20 minutes is capped" }
    check(DecodeBudget.millis(Long.MAX_VALUE) == DecodeBudget.MAX_MS) { "absurd duration is capped" }
    println("PASS decode budget scales with duration and stays bounded")
}
