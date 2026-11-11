package ru.neurostenographer.core

fun testNemotronVoiceProfiles() {
    val width = 3
    val frames = 120
    val evidence = FloatArray(frames * width)
    // A first 3s, B next 3s, A returns. Includes 240 ms of overlapped voices.
    for (i in 0 until frames) {
        val vector = if (i < 38 || i >= 78) floatArrayOf(1f, 0f, 0f)
                     else floatArrayOf(0f, 1f, 0f)
        vector.copyInto(evidence, i * width)
    }
    val turns = listOf(ClusterTurn(0f, 3.0f, 4), ClusterTurn(3f, 6.2f, 7),
        ClusterTurn(6.2f, 9.6f, 4), ClusterTurn(2.80f, 3.04f, 7))
    val prints = NemotronVoiceProfiles.aggregate(turns, evidence, frames, 9600L, width)
    check(prints.size == 2 && prints[0].localSpeakerId == "Speaker 1" &&
        prints[1].localSpeakerId == "Speaker 2")
    check(prints[0].cleanSpeechMs >= 4000 && prints[1].cleanSpeechMs >= 1500)
    check(prints[0].embedding[0] > 30f && prints[1].embedding[1] > 15f)
    // One sub-second phrase must not produce a voice identity.
    val tiny = NemotronVoiceProfiles.aggregate(listOf(ClusterTurn(0f, 0.5f, 0)),
        FloatArray(10 * width) { 1f }, 10, 800, width)
    check(tiny.isEmpty())
    // Overlapping speakers should contribute no voice evidence.
    val both = NemotronVoiceProfiles.aggregate(
        listOf(ClusterTurn(0f, 2f, 0), ClusterTurn(0f, 2f, 1)),
        FloatArray(30 * width) { 1f }, 30, 2400, width)
    check(both.isEmpty())
    check(runCatching { NemotronVoiceProfiles.aggregate(emptyList(), FloatArray(1), 10, 800, width) }.isFailure)
    println("PASS C2 voice profiles: clean frames, overlapping voices, repeated speaker, short speech, bounds")
}
