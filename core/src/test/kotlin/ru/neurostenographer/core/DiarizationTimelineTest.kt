package ru.neurostenographer.core

fun testDiarizationTimeline() {
    val raw = listOf(ClusterTurn(4f, 6f, 19), ClusterTurn(2f, 4f, 7), ClusterTurn(0f, 2f, 19))
    val turns = DiarizationTimeline.canonicalize(raw, 6000)
    check(turns.map { it.speakerId } == listOf("Speaker 1", "Speaker 2", "Speaker 1"))
    check(turns == DiarizationTimeline.canonicalize(raw.reversed(), 6000))
    val windows = DiarizationTimeline.windows(turns, 6000)
    check(windows == listOf(AudioWindow(0, 2000), AudioWindow(2000, 4000), AudioWindow(4000, 6000)))
    val attributed = TranscriptFusion.attributeChunks(windows.map { RecognizedChunk(it.startMs, it.endMs, "test") }, turns)
    check(attributed.map { it.speakerId } == turns.map { it.speakerId })
    val overlapping = DiarizationTimeline.canonicalize(listOf(ClusterTurn(0f, 4f, 2), ClusterTurn(1f, 3f, 3)), 4000)
    val overlapText = TranscriptFusion.attributeChunks(listOf(RecognizedChunk(1000, 3000, "mixed")), overlapping).single()
    check(overlapText.overlappingSpeech && overlapText.speakerId == null && !overlapText.attributionReliable)
    check(TranscriptExport.srt(listOf(overlapText)).contains("[перекрытие речи]"))
    check(TranscriptExport.json(listOf(overlapText)).contains("\"overlapping_speech\": true"))
    check(DiarizationTimeline.canonicalize(listOf(ClusterTurn(0f, 0.2f, 1), ClusterTurn(0f, 1f, -1)), 1000)
        .none { it.attributionEligible })
    for (interruption in listOf(ClusterTurn(0.4f, 0.6f, 2), ClusterTurn(0.4f, 0.8f, -1))) {
        val interrupted = DiarizationTimeline.canonicalize(listOf(ClusterTurn(0f, 2f, 1), interruption), 2000)
        val segment = TranscriptFusion.attributeChunks(listOf(RecognizedChunk(400, 600, "mixed")), interrupted).single()
        check(segment.speakerId == null && segment.overlappingSpeech && !segment.attributionReliable)
    }
    check(DiarizationTimeline.speechWindows(listOf(ClusterTurn(0f, 0.2f, 1), ClusterTurn(1f, 2f, -1)), 3000) ==
        listOf(AudioWindow(0, 200), AudioWindow(1000, 2000)))
    check(DiarizationTimeline.speechWindows(emptyList(), 3000).isEmpty())
    check(DiarizationTimeline.windows(emptyList(), 40001) == listOf(AudioWindow(0, 20000), AudioWindow(20000, 40000)))
    check(DiarizationTimeline.canonicalize(listOf(ClusterTurn(1f, 11f, 2)), 2000).single().endMs == 2000L)
    for (bad in listOf(ClusterTurn(Float.NaN, 1f, 0), ClusterTurn(0f, Float.POSITIVE_INFINITY, 0),
        ClusterTurn(2f, 1f, 0), ClusterTurn(-1f, 1f, 0))) {
        try { DiarizationTimeline.canonicalize(listOf(bad), 1000); error("Invalid turn accepted") }
        catch (_: IllegalArgumentException) { }
    }
    val unknown = TranscriptFusion.attributeChunks(listOf(RecognizedChunk(0, 500, "unknown")), emptyList()).single()
    check(unknown.speakerId == null && !unknown.attributionReliable)
    println("PASS diarization timeline: global A-B-A, order, overlap unknown, short/negative unknown, clipping, invalid native intervals, windows")
}
