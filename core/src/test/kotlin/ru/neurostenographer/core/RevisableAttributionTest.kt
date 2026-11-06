package ru.neurostenographer.core

fun testRevisableAttribution() {
    val text = RealtimeTranscript()
    text.add(SampleSpan(0, 32000, 32000), listOf(RecognizedWord(100, 400, "один"),
        RecognizedWord(900, 1200, "два")), null)
    check(text.snapshot(listOf(SpeakerTurn(0, 2000, "A")), 10000).single().text == "один два")
    // Even far beyond the former 650-ms freeze boundary, split without losing word times.
    val revised = text.snapshot(listOf(SpeakerTurn(0, 600, "B"), SpeakerTurn(600, 2000, "C")), 100000)
    check(revised.map { it.speakerId } == listOf("B", "C"))
    check(revised.map { it.startMs } == listOf(100L, 900L))
    check(text.snapshot(emptyList(), 100000).all { it.speakerId == null })
    val overlap = text.snapshot(listOf(SpeakerTurn(0, 2000, "B"), SpeakerTurn(800, 1300, "C")), 100000)
    check(overlap.last().overlappingSpeech && overlap.last().speakerId == null)
    check(overlap.joinToString(" ") { it.text } == "один два")
    val old = listOf(ClusterTurn(0f, 1f, 0), ClusterTurn(1f, 2f, 1), ClusterTurn(2f, 3f, 0))
    val swapped = old.map { it.copy(cluster = 1 - it.cluster) }
    check(SpeakerIdentity.align(swapped, old) == old)
    val split = listOf(ClusterTurn(0f, 1f, 0), ClusterTurn(1f, 2f, 1), ClusterTurn(2f, 3f, 2))
    check(SpeakerIdentity.align(split, old).map { it.cluster }.distinct().size == 3)
    // Historical logits change slot; all eight channels must be revised, not OR-ed forever.
    var call = 0
    val runner = NemotronChunkRunner { _, frames, _, _, context ->
        call++
        val n = context + (frames + 7) / 8
        val logits = FloatArray(n * 64) { if (it % 8 == if (call == 1) 0 else 1) 1f else -1f }
        NemotronStep(logits, n * 8, FloatArray(n * 512), n)
    }
    val stream = NemotronStreaming(FloatArray(128 * 257), FloatArray(400), FloatArray(512), runner)
    stream.step(65536, false) { _, n -> FloatArray(n) }
    check(stream.snapshot(65536).map { it.cluster }.distinct() == listOf(0))
    stream.step(130000, true) { _, n -> FloatArray(n) }
    check(stream.snapshot(130000).map { it.cluster }.distinct() == listOf(1))
    check(stream.revisedFrames == 360L)
    val windows = RealtimeTranscript()
    windows.add(SampleSpan(0, 16000, 16000), listOf(RecognizedWord(100, 400, "a")), null)
    windows.add(SampleSpan(48000, 64000, 64000), listOf(RecognizedWord(3100, 3400, "b")), null)
    val sweep = windows.snapshot(listOf(SpeakerTurn(1500, 2000, "gap"), SpeakerTurn(3000, 3500, "B"),
        SpeakerTurn(0, 4000, "A")), 5000)
    check(sweep.first().speakerId == "A" && sweep.last().overlappingSpeech)
    check(sweep.last().speakerId == null && sweep.last().text == "b")
    call = 0
    val offline = NemotronStreaming(FloatArray(128 * 257), FloatArray(400), FloatArray(512), runner,
        NemotronChunkConfig.OFFLINE)
    offline.step(500000, false) { _, n -> FloatArray(n) }
    offline.step(600000, true) { _, n -> FloatArray(n) }
    check(offline.revisedFrames == 0L)
    check(offline.snapshot(600000).map { it.cluster }.distinct().sorted() == listOf(0, 1))
    val hour = RealtimeTranscript()
    val turns = (0 until 1800).map { i ->
        val ms = i * 2000L
        hour.add(SampleSpan(ms * 16, (ms + 2000) * 16, (ms + 2000) * 16),
            (0..4).map { j -> RecognizedWord(ms + j * 300 + 100, ms + j * 300 + 300, "w$i-$j") }, null)
        SpeakerTurn(ms, ms + 2000, "S${i % 4}")
    }
    val began = System.nanoTime()
    val first = hour.snapshot(turns, 3600000)
    val corrected = hour.snapshot(turns.map { it.copy(speakerId = "R" + it.speakerId) }, 3600000)
    check(first.map { it.text } == corrected.map { it.text })
    check(corrected.size == 1800 && hour.pendingWords == 9000)
    check(corrected.all { it.speakerId!!.startsWith("R") })
    println("PASS hour text revision: 9000 immutable words, 1800 windows, 4 IDs; two snapshots ms=" + (System.nanoTime() - began) / 1000000)
    println("PASS revisable attribution: late split, immutable word times, revoke on failure, overlap, bijective identity, historical replacement")
}
