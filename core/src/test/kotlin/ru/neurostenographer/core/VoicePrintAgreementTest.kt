package ru.neurostenographer.core

fun testVoicePrintAgreement() {
    // Two independent, non-overlapping excerpts are needed; an isolated
    // 3-second prefix no longer grants identity to a whole 5-minute block.
    val tooShort = CleanSpeakerFrames.separate(IntArray(149) { 0 }, 0)
    check(tooShort == null)
    val timeline = IntArray(600) { index ->
        if (index in 260..270 || index in 400..414) -1 else 0
    }
    val parts = requireNotNull(CleanSpeakerFrames.separate(timeline, 0))
    check(parts.early.size == 200 && parts.late.size == 200)
    check(parts.early.all { timeline[it] == 0 } &&
        parts.late.all { timeline[it] == 0 })
    check(parts.early.toSet().intersect(parts.late.toSet()).isEmpty())
    check(parts.early.last() < parts.late.first())
    check(CleanSpeakerFrames.separate(IntArray(200) { 0 }, 1) == null)
    // Distinct, time-separated profiles of the same voice may be merged.
    val x = floatArrayOf(1f, 0f, 0f)
    val y = floatArrayOf(0.985f, 0.17f, 0f)
    val merged = requireNotNull(VoicePrintAgreement.mergeIfConsistent(x, y))
    check(merged.size == 3 && merged[0] > 0.98f && merged[1] > 0.08f)
    check(x.contentEquals(floatArrayOf(1f, 0f, 0f)))
    // A changed voice in the same C2 slot must NOT get a global fingerprint.
    check(VoicePrintAgreement.mergeIfConsistent(
        floatArrayOf(1f, 0f), floatArrayOf(0f, 1f)) == null)
    check(VoicePrintAgreement.mergeIfConsistent(
        floatArrayOf(1f, 0f), floatArrayOf(0.80f, 0.60f)) == null)
    check(VoicePrintAgreement.mergeIfConsistent(
        floatArrayOf(Float.NaN, 1f), floatArrayOf(1f, 0f)) == null)
    check(VoicePrintAgreement.mergeIfConsistent(
        floatArrayOf(0f, 0f), floatArrayOf(1f, 0f)) == null)
    check(VoicePrintAgreement.mergeIfConsistent(
        floatArrayOf(1f, 0f), floatArrayOf(1f, 0f, 0f)) == null)
    println("PASS independent time-separated speaker samples, stable voice agreement and mismatched speaker refusal")
}
