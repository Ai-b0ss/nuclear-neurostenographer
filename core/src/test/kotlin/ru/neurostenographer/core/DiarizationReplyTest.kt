package ru.neurostenographer.core

fun testDiarizationReply() {
    fun reply(starts: LongArray = longArrayOf(0, 800), ends: LongArray = longArrayOf(500, 1500),
              speakers: List<String> = listOf("Speaker 1", "Speaker 2"),
              eligible: BooleanArray = booleanArrayOf(true, true),
              ws: LongArray = longArrayOf(0, 800), we: LongArray = longArrayOf(500, 1500),
              load: Long = 1, process: Long = 2) =
        DiarizationReply.validate(2000, starts, ends, speakers, eligible, ws, we, load, process)
    val valid = reply()
    check(valid.turns.map { it.speakerId } == listOf("Speaker 1", "Speaker 2"))
    check(valid.windows == listOf(AudioWindow(0, 500), AudioWindow(800, 1500)))
    var negatives = 0
    fun bad(block: () -> Unit) {
        try { block(); error("Malformed worker reply accepted") }
        catch (_: IllegalArgumentException) { negatives++ }
    }
    bad { reply(starts = longArrayOf(0)) }
    bad { reply(eligible = booleanArrayOf(true)) }
    bad { reply(we = longArrayOf(500)) }
    bad { reply(ends = longArrayOf(500, 2001)) }
    bad { reply(starts = longArrayOf(-1, 800)) }
    bad { reply(ends = longArrayOf(0, 1500)) }
    bad { reply(starts = longArrayOf(800, 0), ends = longArrayOf(1500, 500)) }
    bad { reply(speakers = listOf("Alice", "Speaker 2")) }
    bad { reply(speakers = listOf("Speaker 0", "Speaker 2")) }
    bad { reply(speakers = listOf("Unknown", "Speaker 2")) }
    bad { reply(ends = longArrayOf(250, 1500)) }
    bad { reply(load = -1) }
    bad { reply(process = -1) }
    bad { reply(ws = longArrayOf(0), we = longArrayOf(500)) } // silently dropped speech
    bad { reply(ws = longArrayOf(0), we = longArrayOf(1500)) } // decoded silence gap
    bad { reply(ws = longArrayOf(0, 400), we = longArrayOf(500, 1500)) }
    bad { reply(ws = longArrayOf(0, 800), we = longArrayOf(500, 2001)) }
    bad { reply(ws = longArrayOf(0, Long.MAX_VALUE), we = longArrayOf(500, Long.MIN_VALUE + 100)) }
    bad { reply(starts = LongArray(2001), ends = LongArray(2001) { 500 },
        speakers = List(2001) { "Speaker 1" }, eligible = BooleanArray(2001)) }
    bad { reply(ws = LongArray(2001), we = LongArray(2001) { 500 }) }
    val silence = DiarizationReply.validate(2000, longArrayOf(), longArrayOf(), emptyList(),
        booleanArrayOf(), longArrayOf(), longArrayOf(), 0, 0)
    check(silence.turns.isEmpty() && silence.windows.isEmpty())
    val uncertain = DiarizationReply.validate(1000, longArrayOf(0, 400), longArrayOf(200, 900),
        listOf("Unknown", "Speaker 1"), booleanArrayOf(false, true),
        longArrayOf(0, 400), longArrayOf(200, 900), 0, 0)
    val fused = TranscriptFusion.attributeChunks(listOf(RecognizedChunk(0, 200, "текст")), uncertain.turns)
    check(fused.single().speakerId == null && !fused.single().attributionReliable)
    val overlap = DiarizationReply.validate(2000, longArrayOf(0, 500), longArrayOf(1000, 1500),
        listOf("Speaker 1", "Speaker 2"), booleanArrayOf(true, true),
        longArrayOf(0, 500, 1000), longArrayOf(500, 1000, 1500), 0, 0)
    val mixed = TranscriptFusion.attributeChunks(listOf(RecognizedChunk(500, 1000, "текст")), overlap.turns).single()
    check(mixed.overlappingSpeech && mixed.speakerId == null && !mixed.attributionReliable)
    check(negatives == 20)
    println("PASS diarization IPC validation (20 corruptions, speech gaps, silence, unknown and overlap)")
}
