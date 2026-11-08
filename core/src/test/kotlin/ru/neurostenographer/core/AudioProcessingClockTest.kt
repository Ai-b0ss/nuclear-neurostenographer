package ru.neurostenographer.core

fun testAudioProcessingClock() {
    val first = AudioProcessingClock(3_600_000, 0, 300_000, 1_000)
    check(first.positionAt(1_000) == 0L)
    check(first.positionAt(12_000) == 22_000L)
    check(first.positionAt(101_000) == 200_000L)
    check(first.positionAt(300_000) == 299_000L)
    check(first.waitingForCheckpoint(300_000))
    check(!first.calibrated && first.remainingWallMs(1_000) == 1_800_000L)
    check(first.positionAt(500) == 0L)

    val measured = first.advance(300_000, 600_000, 151_000, 150_000)
    check(measured.calibrated && measured.audioPerWallMs == 2.0)
    check(measured.positionAt(161_000) == 320_000L)
    check(measured.remainingWallMs(161_000) == 1_640_000L)

    val slow = measured.advance(600_000, 900_000, 451_000, 300_000)
    check(slow.audioPerWallMs in 1.54..1.56)
    check(slow.positionAt(451_000) == 600_000L)
    check(slow.positionAt(452_000) > slow.positionAt(451_000))
    val silent = slow.advance(900_000, 1_200_000, 453_000)
    check(silent.calibrated && silent.audioPerWallMs == slow.audioPerWallMs)
    val done = silent.advance(3_600_000, 3_600_000, 600_000, 100_000)
    check(done.positionAt(Long.MAX_VALUE) == 3_600_000L)
    check(done.fractionAt(600_000) == 1f)
    check(done.remainingWallMs(600_000) == 0L)
    check(runCatching { first.advance(-1, 100, 900) }.isFailure)
    check(runCatching { first.advance(400_000, 200_000, 900) }.isFailure)
    println("PASS real-time offline processing timer")
}
