package ru.neurostenographer.core

fun testCleanSpeakerFrames() {
    // A high-confidence long speaker is interrupted by a low-confidence
    // overlapping 200ms turn: those samples must NEVER enter voice evidence.
    val bad = CleanSpeakerFrames.select(listOf(
        SpeakerTurn(0, 4000, "Speaker 1"),
        SpeakerTurn(1800, 2000, "Speaker 2", attributionEligible = false)
    ), 100, 4000)
    check(bad.speakerIds == listOf("Speaker 1"))
    check(bad.owners.count { it == 0 } == 95)
    check((45 until 50).all { bad.owners[it] == -1 })
    check(bad.owners[44] == 0 && bad.owners[50] == 0)

    // An ineligible unknown fragment crossing a frame boundary
    // contaminates BOTH adjacent frames even when just two milliseconds.
    val tinyOverlap = CleanSpeakerFrames.select(listOf(
        SpeakerTurn(0, 4000, "a"),
        SpeakerTurn(1999, 2001, "uncertain", attributionEligible = false)
    ), 100, 4000)
    check(tinyOverlap.owners[49] == -1 && tinyOverlap.owners[50] == -1)
    check(tinyOverlap.owners.count { it == 0 } == 98)

    // Eligible A and B both cover these samples; neither may harvest them.
    val twoSpeakers = CleanSpeakerFrames.select(listOf(
        SpeakerTurn(0, 4000, "a"),
        SpeakerTurn(2000, 3000, "b")
    ), 100, 4000)
    check(twoSpeakers.speakerIds == listOf("a", "b"))
    check((50 until 75).all { twoSpeakers.owners[it] == -1 })
    check(twoSpeakers.owners.count { it == 0 } == 75)
    check(twoSpeakers.owners.count { it == 1 } == 0)

    // A non-aligned long turn and an ineligible turn overlapping its start.
    val edges = CleanSpeakerFrames.select(listOf(
        SpeakerTurn(7, 151, "voice"),
        SpeakerTurn(1, 8, "noise", attributionEligible = false)
    ), 4, 160)
    check(edges.owners.contentEquals(intArrayOf(-1, 0, 0, -1)))

    // Timeline outside decoded audio: fail-closed, not "use available bits".
    val corrupted = CleanSpeakerFrames.select(listOf(
        SpeakerTurn(0, 4001, "a")
    ), 100, 4000)
    check(corrupted.speakerIds.isEmpty())
    check(corrupted.owners.all { it == -1 })

    val noTurns = CleanSpeakerFrames.select(emptyList(), 2, 80)
    check(noTurns.speakerIds.isEmpty() && noTurns.owners.all { it == -1 })
    println("PASS clean speaker frames: ineligible overlap, sub-frame boundary, colliding voices, corrupt timelines")
}
