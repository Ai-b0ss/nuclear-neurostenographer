package ru.neurostenographer.core

/** Authored transport invariants, not a substitute for the native speaker-quality gate. */
fun testRealtimeChunkBoundaries() {
    val filters = FloatArray(128 * 257) { if (it % 257 == 3) 1f else 0f }
    val hann = FloatArray(400) { 1f }
    for (size in listOf(160, 161, 65536, 536119)) {
        val pcm = FloatArray(size) { ((it * 31 % 997) - 498) / 997f }
        val full = NemotronMel(pcm, filters, hann)
        val expectedMel = FloatArray(full.frames * 128)
        full.write(0, full.frames, expectedMel)
        var start = 0
        var available = 0L
        var eof = false
        var chunk = 45
        val runner = NemotronChunkRunner { mel, frames, length, history, context ->
            // Before compression these rows must remain chronological, even across a FIFO pop.
            check(context == start)
            check((0 until context).all { history[it * 512] == it.toFloat() })
            check(mel.indices.all { mel[it] == expectedMel[start * 8 * 128 + it] })
            check(length == if (eof) minOf(frames, full.frames - 1 - start * 8) else frames)
            val newFrames = (frames + 7) / 8
            val total = context + newFrames
            val logits = FloatArray(total * 64) { -1f }
            for (f in 0 until total * 8) {
                // Two independent channels, an overlap region, and an unknown/silent region.
                val phase = f % 400
                if (phase < 100) logits[f * 8] = 1f
                if (phase in 50..149) logits[f * 8 + 1] = 1f
            }
            val embeds = FloatArray(total * 512) { (it / 512).toFloat() }
            start += minOf(chunk, newFrames)
            NemotronStep(logits, total * 8, embeds, total)
        }
        val stream = NemotronStreaming(filters, hann, FloatArray(512), runner)
        fun read(first: Long, count: Int): FloatArray {
            check(first >= 0 && first + count <= available) { "Future PCM read" }
            return pcm.copyOfRange(first.toInt(), first.toInt() + count)
        }
        while (available < size) {
            available = minOf(size.toLong(), available + 512)
            while (stream.canStep(available, false)) {
                stream.step(available, false, ::read)
                if (stream.calls == 3) {
                    val old = stream.contextFrames
                    stream.config = NemotronChunkConfig.FALLBACK; chunk = 120
                    check(stream.contextFrames == old)
                }
            }
        }
        eof = true
        while (stream.canStep(available, true)) stream.step(available, true, ::read)
        check(stream.committedSamples == full.frames * 160L)
        val turns = stream.snapshot(available)
        // Inspect each output frame independently: duplicates, gaps, lost overlap and invented
        // speakers all fail. Padding must never escape the actual PCM duration.
        check(turns.all { it.endSeconds <= size / 16000f })
        for (f in 0 until size / 160) {
            val time = (f + 0.5f) / 100
            val active = turns.filter { it.startSeconds <= time && time < it.endSeconds }.map { it.cluster }
            val expected = buildList {
                if (f % 400 < 100) add(0)
                if (f % 400 in 50..149) add(1)
            }
            check(active.sorted() == expected) { "Lost/duplicate output at frame $f" }
        }
    }
    println("PASS realtime chunk boundaries: exact mel slices, causal PCM, EOF, cache identities, adaptation, overlap/unknown, no duplicate output")
}
