package ru.neurostenographer.core

private fun test(label: String, action: () -> Unit) {
    action()
    println("PASS " + label)
}

fun main() {
    testPcmWav()
    testPcmStreaming()
    testPcm16WavWriter()
    testBoundedWavRecorder()
    testAudioSnapshots()
    testTranscriptDocument()
    testVerifiedModelBundle()
    testDiarizationTimeline()
    testDecodeBudget()
    test("A B A speaker returns") {
        val turns = listOf(SpeakerTurn(2000, 2900, "B"), SpeakerTurn(4000, 5000, "A"), SpeakerTurn(0, 1500, "A"))
        val words = listOf(RecognizedWord(4050, 4500, "согласен"), RecognizedWord(100, 600, "привет"), RecognizedWord(2100, 2500, "да"))
        check(TranscriptFusion.attributeWords(words, turns).map { it.speakerId } == listOf("A", "B", "A"))
    }
    test("unknown without diarization") {
        val result = TranscriptFusion.attributeWords(listOf(RecognizedWord(0, 500, "текст")), emptyList())
        check(result.single().speakerId == null && !result.single().attributionReliable)
    }
    test("overlap detected instead of invented identity") {
        val turns = listOf(SpeakerTurn(0, 1000, "A"), SpeakerTurn(300, 900, "B"))
        val result = TranscriptFusion.attributeWords(listOf(RecognizedWord(400, 700, "да")), turns).single()
        check(result.speakerId == null && result.overlappingSpeech)
    }
    test("adjacent speakers not overlap") {
        val result = TranscriptFusion.attributeWords(
            listOf(RecognizedWord(400, 600, "слово")),
            listOf(SpeakerTurn(0, 300, "A"), SpeakerTurn(300, 900, "B"))
        ).single()
        check(result.speakerId == "B" && !result.overlappingSpeech)
    }
    test("adjacent fragments of one speaker merge into a reply") {
        fun s(a: Long, b: Long, who: String?, text: String, reliable: Boolean = true, overlap: Boolean = false) =
            TranscriptSegment(a, b, who, text, overlap, reliable)
        val merged = TranscriptFusion.mergeReplies(listOf(s(0, 20_000, "A", "раз"), s(20_000, 25_000, "A", "два"),
            s(25_000, 26_000, "B", "три"), s(26_000, 27_000, "A", "четыре")))
        check(merged.map { it.text } == listOf("раз два", "три", "четыре"))
        check(merged[0].startMs == 0L && merged[0].endMs == 25_000L)
        check(TranscriptFusion.mergeReplies(listOf(s(0, 1000, "A", "x"), s(3000, 4000, "A", "y"))).size == 2)
        check(TranscriptFusion.mergeReplies(listOf(s(0, 1000, null, "x", false), s(1000, 2000, null, "y", false))).size == 2)
        check(TranscriptFusion.mergeReplies(listOf(s(0, 1000, "A", "x"), s(1000, 2000, "A", "y", false))).size == 2)
        check(TranscriptFusion.mergeReplies(listOf(s(0, 40_000, "A", "x"), s(40_000, 70_000, "A", "y"))).size == 2)
    }
    test("forced cuts move to a nearby pause and keep the audio covered") {
        val samples = FloatArray(16000 * 50) { 0.5f }
        for (i in 16000 * 19 until 16000 * 19 + 1600) samples[i] = 0f // pause at 19.0–19.1 s
        val windows = listOf(AudioWindow(0, 20_000), AudioWindow(20_000, 40_000), AudioWindow(40_000, 50_000))
        val refined = QuietCuts.refine(windows, samples)
        check(refined[0].endMs in 19_000..19_100) { refined }
        check(refined.first().startMs == 0L && refined.last().endMs == 50_000L)
        check(refined.zipWithNext().all { (a, b) -> a.endMs == b.startMs })
        check(refined.all { it.endMs - it.startMs in 100..20_000 }) { refined }
        // Uniform audio keeps the original cuts; turn boundaries and short pieces are untouched.
        check(QuietCuts.refine(windows, FloatArray(16000 * 50) { 0.5f }) == windows)
        val shortPieces = listOf(AudioWindow(0, 5_000), AudioWindow(5_000, 9_000))
        check(QuietCuts.refine(shortPieces, samples) == shortPieces)
        // A long final piece limits how far the cut may move.
        val tail = listOf(AudioWindow(0, 20_000), AudioWindow(20_000, 39_500))
        check(QuietCuts.refine(tail, samples).all { it.endMs - it.startMs <= 20_000 })
    }
    test("long ASR chunk crossing turn ambiguous") {
        val result = TranscriptFusion.attributeChunks(
            listOf(RecognizedChunk(0, 2000, "да, хорошо")),
            listOf(SpeakerTurn(0, 1000, "A"), SpeakerTurn(1000, 2000, "B"))
        ).single()
        check(result.speakerId == null)
    }
    test("punctuation and export") {
        val items = TranscriptFusion.attributeWords(
            listOf(RecognizedWord(0, 100, "Привет"), RecognizedWord(100, 120, ","), RecognizedWord(200, 400, "мир")),
            listOf(SpeakerTurn(0, 500, "A"))
        )
        check(items.single().text == "Привет, мир")
        check(TranscriptExport.json(items).contains("\"speaker_id\": \"A\""))
        check(TranscriptExport.srt(items).contains("-->"))
        check(TranscriptExport.txt(items).contains("Привет, мир"))
        check(TranscriptExport.json(items, TranscriptProvenance("test", "revision", "input_windows", "not_run"))
            .contains("\"timestamp_source\": \"input_windows\""))
    }
    testWavContainer()
    testDiarizationReply()
    println("16 CORE TEST GROUPS PASSED")
}
