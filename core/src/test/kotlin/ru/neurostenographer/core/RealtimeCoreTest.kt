package ru.neurostenographer.core

fun testRealtimeCore() {
    testRealtimeChunkBoundaries()
    val directory = java.nio.file.Files.createTempDirectory("realtime-journal").toFile()
    try {
        val sessionDir = java.io.File(directory, "realtime/session").apply { mkdirs() }
        val wav = java.io.File(sessionDir, "capture.wav")
        val journal = ru.neurostenographer.app.RealtimeJournal(wav)
        var at = 0L
        val total = 70 * 16000L + 127
        while (at < total) {
            val count = minOf(512L, total - at).toInt()
            journal.append(ShortArray(count) { (at + it).toShort() }, count)
            at += count
        }
        val early = journal.read(0, 16000)
        check(early.indices.all { early[it] == it.toShort() / 32768f })
        check(journal.diskReads == 1)
        val recent = journal.read(total - 10000, 10000)
        check(recent.indices.all { recent[it] == (total - 10000 + it).toShort() / 32768f })
        check(journal.diskReads == 1)
        journal.finish(); journal.close()
        check(java.io.File(sessionDir, "capture-finalized.txt").isFile)
        check(wav.length() == 44 + total * 2)
        val kept = wav.inputStream().use { PcmWav.read(it) }
        check(kept.samples.size.toLong() == total)
        check(kept.samples.indices.all { kept.samples[it] == it.toShort() / 32768f })
        check(runCatching { ru.neurostenographer.app.RealtimeJournal(wav) }.isFailure)
        check(wav.length() == 44 + total * 2) // no accidental reuse/truncation
        val interruptedDir = java.io.File(directory, "realtime/interrupted").apply { mkdirs() }
        val interrupted = java.io.File(interruptedDir, "capture.wav")
        ru.neurostenographer.app.RealtimeJournal(interrupted).use { open ->
            repeat(10) { open.append(ShortArray(512) { 37 }, 512) }
        }
        check(interrupted.length() == 10284L)
        check(ru.neurostenographer.app.RealtimeJournal.recover(interrupted) == 5120L)
        check(interrupted.inputStream().use { PcmWav.read(it) }.samples.all { it == 37 / 32768f })
    } finally {
        directory.walkBottomUp().forEach { it.delete() }
    }
    val history = RealtimeTranscript()
    repeat(1800) { i ->
        val startMs = i * 2000L
        history.add(SampleSpan(startMs * 16, (startMs + 2000) * 16, (startMs + 2000) * 16),
            listOf(RecognizedWord(startMs + 100, startMs + 500, "слово")), null)
        val turns = listOf(SpeakerTurn(0, startMs + 2000, "A"))
        val snapshot = history.snapshot(turns, startMs + 2000)
        check(snapshot.sumOf { it.text.split(' ').size } == i + 1)
        check(history.pendingWords <= 1 && history.stableEntries == i)
        val immediate = history.snapshot(turns, startMs + 2000, initialUnknown = true)
        check(immediate.last().speakerId == null)
        check(immediate.dropLast(1).all { it.speakerId == "A" })
    }
    val overlap = RealtimeTranscript()
    overlap.add(SampleSpan(0, 16000, 16000), listOf(RecognizedWord(400, 700, "да")), null)
    val overlapped = overlap.snapshot(listOf(SpeakerTurn(0, 1000, "A"), SpeakerTurn(300, 900, "B")), 2000).single()
    check(overlapped.speakerId == null && overlapped.overlappingSpeech)
    val ring = RealtimeRing(1024)
    ring.append(ShortArray(700) { it.toShort() })
    check(ring.read(0, 700)!!.indices.all { ring.read(it.toLong(), 1)!![0] == it / 32768f })
    ring.append(ShortArray(700) { (it + 700).toShort() })
    check(ring.read(0, 1) == null && ring.read(1400, 1) == null)
    check(ring.read(400, 1000)!!.indices.all { ring.read((it + 400).toLong(), 1)!![0] == (it + 400) / 32768f })

    for (minutes in listOf(20, 60)) for (pause in listOf(300, 500)) {
        val segmenter = RealtimePhrases(pause)
        val spans = mutableListOf<SampleSpan>()
        var at = 0L
        val total = minutes * 60 * 16000L
        while (at < total) {
            val count = minOf(512L, total - at).toInt()
            spans += segmenter.accept(count, true) { _, size -> size - 16000 }
            at += count
        }
        spans += segmenter.finish()
        check(spans.first().start == 0L && spans.last().end == total)
        check(spans.sumOf { it.end - it.start } == total)
        check(spans.zipWithNext().all { (a, b) -> a.end == b.start })
        check(spans.all { it.end - it.start <= 240000 })
        check(segmenter.finish().isEmpty())
    }
    for (pause in listOf(300, 500)) {
        val silent = RealtimePhrases(pause)
        repeat(1000) { check(silent.accept(512, false) { _, size -> size }.isEmpty()) }
        check(silent.finish().isEmpty())
        val short = RealtimePhrases(pause)
        check(short.accept(512, true) { _, size -> size }.isEmpty())
        repeat(30) { check(short.accept(512, false) { _, size -> size }.isEmpty()) }
        val words = RealtimePhrases(pause)
        repeat(10) { words.accept(512, true) { _, size -> size } }
        val out = (0..30).flatMap { words.accept(512, false) { _, size -> size } }
        check(out.size == 1 && out[0].end == 10 * 512L + 3200)
    }
    val queue = RealtimeQueue()
    repeat(3) { queue.add(SampleSpan(it * 100L, it * 100L + 50, it * 100L + 50)) }
    check(queue.adapt(0) && queue.peak == 3)
    check(runCatching { queue.add(SampleSpan(500, 550, 550)) }.isFailure)
    repeat(3) { check(queue.next()!!.start == it * 100L) }
    check(queue.next() == null && queue.adapt(0))
    queue.clear()
    check(RealtimeQueue().adapt(80001) && RealtimeQueue().adapt(0, 2))

    // Stateful cache pressure: independently bounded despite 1000 chunks of 45 frames.
    val cache = NemotronSpeakerCache(FloatArray(512), 264, 222)
    repeat(1000) { call ->
        val frames = cache.contextFrames() + 45
        val logits = FloatArray(frames * 8 * 8) { if (it % 8 == call % 3) 2f else -2f }
        val embeds = FloatArray(frames * 512) { (it % 512) / 512f }
        cache.update(NemotronStep(logits, frames * 8, embeds, frames), 45)
        check(cache.contextFrames() <= 528)
        check(cache.context().size == cache.contextFrames() * 512)
    }
    var outputCursor = 0
    val runner = NemotronChunkRunner { _, melFrames, _, _, context ->
        val emb = (melFrames + 7) / 8
        val frames = (context + emb) * 8
        val logits = FloatArray(frames * 8) { -1f }
        for (f in context * 8 until frames) logits[f * 8 + (outputCursor / 720) % 2] = 1f
        outputCursor += 360
        NemotronStep(logits, frames, FloatArray((context + emb) * 512), context + emb)
    }
    val stream = NemotronStreaming(FloatArray(128 * 257), FloatArray(400), FloatArray(512), runner)
    check(!stream.canStep(65280, false)) // extra STFT future context is required
    check(stream.canStep(65536, false))
    var maxRead = 0L
    fun read(start: Long, size: Int): FloatArray { maxRead = maxOf(maxRead, start + size); return FloatArray(size) }
    stream.step(65536, false, ::read)
    check(maxRead <= 65536 && stream.committedSamples == 57600L)
    val before = stream.contextFrames
    stream.config = NemotronChunkConfig.FALLBACK
    check(stream.contextFrames == before)
    check(runCatching { stream.config = NemotronChunkConfig.OFFLINE }.isFailure)
    while (stream.canStep(200000, true)) stream.step(200000, true, ::read)
    check(stream.snapshot(200000).all { it.endSeconds <= 12.5f })
    check(stream.calls == 2 && stream.contextFrames > before)
    check(!stream.canStep(200000, true))
    val bad = NemotronStreaming(FloatArray(128 * 257), FloatArray(400), FloatArray(512),
        NemotronChunkRunner { _, _, _, _, _ -> NemotronStep(floatArrayOf(Float.NaN), 1, FloatArray(512), 1) })
    check(runCatching { bad.step(65536, false, ::read) }.isFailure)
    check(bad.calls == 0 && bad.contextFrames == 0)
    println("PASS realtime: ring overwrite, causal prefixes, cache continuity/pressure, 20/60-min sample conservation, pauses, silence, short speech, EOF, queue bounds, adaptation")
}
