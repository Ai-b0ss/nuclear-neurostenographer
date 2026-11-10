package ru.neurostenographer.core

fun testSpeakerConsensus() {
    val preview = listOf(ClusterTurn(0f, 1f, 0), ClusterTurn(1f, 3f, 1),
        ClusterTurn(3f, 4f, 0))
    val conflicting = listOf(ClusterTurn(0f, 4f, 0))
    val result = SpeakerConsensus.previewFirst(preview, conflicting)
    check(result.turns == preview)
    check(result.disagreementMs == 2000L)
    check(result.offlineFillMs == 0L)

    val postStop = SpeakerConsensus.offlineFirst(preview, conflicting)
    check(postStop.turns == conflicting)
    check(postStop.disagreementMs == result.disagreementMs)
    check(SpeakerConsensus.offlineFirst(preview, emptyList()).turns == preview)
    check(SpeakerConsensus.offlineFirst(emptyList(), preview).turns == preview)

    val gapPreview = listOf(ClusterTurn(0f, 1f, 0), ClusterTurn(3f, 4f, 0))
    val gapFinal = listOf(ClusterTurn(0f, 4f, 0))
    val filled = SpeakerConsensus.previewFirst(gapPreview, gapFinal)
    check(filled.turns == listOf(ClusterTurn(0f, 4f, 0)))
    check(filled.offlineFillMs == 2000L)

    val overlapping = listOf(ClusterTurn(0f, 2f, 0), ClusterTurn(0.5f, 1.5f, 1))
    check(SpeakerConsensus.previewFirst(overlapping, overlapping).turns == overlapping)
    check(SpeakerConsensus.previewFirst(emptyList(), overlapping).turns == overlapping)
    check(SpeakerConsensus.previewFirst(emptyList(), emptyList()).turns.isEmpty())
    check(runCatching {
        SpeakerConsensus.previewFirst(listOf(ClusterTurn(0f, 1f, 8)), emptyList())
    }.isFailure)

    // Slot alignment is a distinct, mandatory step before consensus.
    val reordered = overlapping.map { it.copy(cluster = 1 - it.cluster) }
    check(SpeakerConsensus.previewFirst(overlapping,
        SpeakerIdentity.align(reordered, overlapping)).turns == overlapping)

    // Hour-long schedule must not allocate one object per 10-ms frame.
    val hour = (0 until 1800).map { i ->
        val start = i * 2f
        ClusterTurn(start, start + 2f, i % 4)
    }
    val hourResult = SpeakerConsensus.previewFirst(hour, hour)
    check(hourResult.turns == hour)
    check(hourResult.disagreementMs == 0L && hourResult.offlineFillMs == 0L)
    println("PASS speaker consensus: conflicts, filling, overlap, alignment, empty/invalid, hour")
}
