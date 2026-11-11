package ru.neurostenographer.core

private fun test(label: String, action: () -> Unit) {
    action()
    println("PASS " + label)
}

fun main() {
    testRealtimeCore()
    testPcmWav()
    testPcmStreaming()
    testPcmFileAudio()
    testPcm16WavWriter()
    testBoundedWavRecorder()
    testAudioSnapshots()
    testTranscriptDocument()
    testTermDictionary()
    testVerifiedModelBundle()
    testDiarizationTimeline()
    testGlobalSpeakerBook()
    testCleanSpeakerFrames()
    testVoicePrintAgreement()
    testDecodeBudget()
    testAudioProcessingClock()
    testShortProcessingEta()
    testDiarizationTimeEstimate()
    testProcessingTimeDisplay()
    testAsrWindowEta()
    testFddtOverlapPlan()
    test("A B A speaker returns") {
        val turns = listOf(SpeakerTurn(2000, 2900, "B"), SpeakerTurn(4000, 5000, "A"), SpeakerTurn(0, 1500, "A"))
        val words = listOf(RecognizedWord(4050, 4500, "согласен"), RecognizedWord(100, 600, "привет"), RecognizedWord(2100, 2500, "да"))
        check(TranscriptFusion.attributeWords(words, turns).map { it.speakerId } == listOf("A", "B", "A"))
    }
    test("token timestamps to words") {
        // GigaAM e2e RNNT through sherpa-onnx 1.12.20: start of each token in seconds from the window start.
        val tokens = arrayOf(" От", "крой", " ", "темп", "ера", "туру", ",", " пожалуйста", ".", " Да", "?")
        val times = floatArrayOf(0.44f, 0.6f, 0.96f, 1.08f, 1.24f, 1.36f, 3.0f, 3.2f, 3.9f, 4.0f, 4.1f)
        val words = TokenWords.words(tokens, times, 10_000, 15_400)!!
        check(words.map { it.text } == listOf("Открой", "температуру,", "пожалуйста.", "Да?")) { words.toString() }
        check(words[0] == RecognizedWord(10_440, 10_840, "Открой"))
        check(words[1].startMs == 10_960L && words[1].endMs == 11_600L) // punctuation does not stretch the word
        check(words[2].endMs == 13_440L && words[3] == RecognizedWord(14_000, 14_240, "Да?"))
        check(TokenWords.words(arrayOf(" Да", " ", ".", " нет"), floatArrayOf(0.1f, 0.3f, 0.4f, 0.5f), 0, 1000)!!
            .map { it.text } == listOf("Да.", "нет"))
        check(TokenWords.words(tokens, null, 0, 6000) == null)
        check(TokenWords.words(tokens, times.copyOf(3), 0, 6000) == null)
        check(TokenWords.words(arrayOf(" а", " б"), floatArrayOf(1f, 0.5f), 0, 6000) == null)
        check(TokenWords.words(arrayOf(" а"), floatArrayOf(0.9f), 0, 500) == listOf(RecognizedWord(499, 500, "а")))
        // A speaker change inside one window: each word goes to its own speaker, the overlap stays unknown.
        val turns = listOf(SpeakerTurn(10_000, 12_000, "A"), SpeakerTurn(11_900, 16_000, "B"))
        val segments = TranscriptFusion.attributeWords(words, turns)
        check(segments.map { it.speakerId to it.text } == listOf("A" to "Открой температуру,", "B" to "пожалуйста. Да?"))
    }
    test("export file names keep dates") {
        check(TranscriptExport.fileBase("Запись 5 нояб., 01:40") == "Запись 5 нояб_ 01_40")
        check(TranscriptExport.fileBase("interview.final.MP3") == "interview_final")
        check(TranscriptExport.fileBase("v1.2 итог") == "v1_2 итог")
        check(TranscriptExport.fileBase(" ... ") == "transcript")
    }
    test("long recording local speaker scope preserves attribution and unknowns") {
        val one = TranscriptSegment(250, 420, "Speaker 1", "слово", attributionReliable = true)
        val shifted = LocalSpeakerScope.shift(one, 300_000L, 0)
        check(shifted.startMs == 300_250L && shifted.endMs == 300_420L)
        check(shifted.speakerId == "Block 1 / Speaker 1" && shifted.attributionReliable)
        val repeated = LocalSpeakerScope.shift(one, 600_000L, 1)
        check(repeated.speakerId == "Block 2 / Speaker 1")
        check(repeated.speakerId != shifted.speakerId)
        val header = TranscriptExport.header(listOf(shifted, repeated), 900_000L)
        check(header.contains("локальных меток: 2") && header.contains("по блокам")) { header }
        val unknown = LocalSpeakerScope.shift(TranscriptSegment(0, 100, null, "неясно"), 300_000L, 0)
        check(unknown.speakerId == null)
        val overlap = LocalSpeakerScope.shift(
            TranscriptSegment(100, 300, null, "оба", true, false, listOf("Speaker 1", "Speaker 2")),
            400_000L, 2)
        check(overlap.speakerId == null)
        check(overlap.overlapSpeakers == listOf("Block 3 / Speaker 1", "Block 3 / Speaker 2"))
        check(TranscriptExport.contestJson(listOf(overlap)).contains("unknown"))
    }
    test("unknown without diarization") {
        val result = TranscriptFusion.attributeWords(listOf(RecognizedWord(0, 500, "текст")), emptyList())
        check(result.single().speakerId == null && !result.single().attributionReliable)
    }
    test("overlap detected instead of invented identity") {
        val turns = listOf(SpeakerTurn(0, 1000, "A"), SpeakerTurn(300, 900, "B"))
        val result = TranscriptFusion.attributeWords(listOf(RecognizedWord(400, 700, "да")), turns).single()
        check(result.speakerId == null && result.overlappingSpeech)
        check(result.overlapSpeakers == listOf("A", "B"))
    }
    test("overlap names both speakers in UI, TXT, SRT and JSON") {
        // A third speaker present in the window but not overlapping is not named.
        val turns = listOf(SpeakerTurn(0, 1000, "Speaker 10"), SpeakerTurn(300, 900, "Speaker 2"), SpeakerTurn(1000, 1200, "Speaker 1"))
        val s = TranscriptFusion.attributeWords(listOf(RecognizedWord(400, 1100, "да")), turns).single()
        check(s.speakerId == null && s.overlapSpeakers == listOf("Speaker 2", "Speaker 10")) { s.toString() }
        check(TranscriptExport.segmentSpeaker(s) == "Говорящий 2 + Говорящий 10")
        check(TranscriptExport.segmentSpeaker(s, mapOf("Speaker 2" to "Анна")) == "Анна + Говорящий 10")
        check(TranscriptExport.txt(listOf(s)).contains("] Говорящий 2 + Говорящий 10: да [перекрытие речи]"))
        check(TranscriptExport.srt(listOf(s)).contains("\nГоворящий 2 + Говорящий 10: да"))
        val json = TranscriptExport.json(listOf(s))
        check(json.contains("\"speaker_id\": null, \"overlap_speaker_ids\": [\"Speaker 2\", \"Speaker 10\"], \"text\"")) { json }
        // Words of different overlap pairs do not merge into one fragment.
        val two = TranscriptFusion.attributeWords(listOf(RecognizedWord(100, 200, "а"), RecognizedWord(250, 350, "б")),
            listOf(SpeakerTurn(0, 400, "A"), SpeakerTurn(0, 220, "B"), SpeakerTurn(240, 400, "C")))
        check(two.map { it.overlapSpeakers } == listOf(listOf("A", "B"), listOf("A", "C"))) { two.toString() }
        // No overlap, no names: unknown stays «Не определён».
        check(TranscriptExport.segmentSpeaker(TranscriptSegment(0, 1, null, "x")) == "Не определён")
        check(!TranscriptExport.json(listOf(TranscriptSegment(0, 1, null, "x"))).contains("overlap_speaker_ids"))
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
    testTopicTitle()
    testVoiceLevel()
    testStreamingPcm16()
    println("20 CORE TEST GROUPS PASSED")
}
