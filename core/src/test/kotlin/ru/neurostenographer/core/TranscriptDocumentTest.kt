package ru.neurostenographer.core

import java.util.Locale

fun testTranscriptDocument() {
    val locale = Locale.getDefault()
    try {
        Locale.setDefault(Locale.forLanguageTag("ar-EG"))
        val items = listOf(TranscriptSegment(123, 456, "Speaker 1", "Привет \"мир\"\nда"),
            TranscriptSegment(3600001, 3600999, null, "перекрытие", true))
        val provenance = TranscriptProvenance("engine", "revision", "input_windows", "failed_worker_unknown_speakers")
        val document = TranscriptDocument(items, 3601000, provenance, listOf("ошибка\tJNI"))
        val json = document.export("json")
        check(json.contains("\"audio_duration_ms\": 3601000"))
        check(json.contains("ошибка\\tJNI") && json.contains("\\\"мир\\\"\\nда"))
        check(json.contains("\"speaker_id\": null") && json.contains("\"overlapping_speech\": true"))
        // The public judge JSON must have exactly the slide's fields, with raw ASR text.
        val judge = document.export("json-contest")
        check(judge.contains("\"transcript\": [") && !judge.contains("\"segments\"") &&
            !judge.contains("\"provenance\"") && !judge.contains("\"speaker_name\"") &&
            !judge.contains("\"text_edited\""))
        check(judge.contains("\"speaker_id\": \"speaker_1\", \"start_ms\": 123, \"end_ms\": 456"))
        check(judge.contains("\"speaker_id\": \"unknown\", \"start_ms\": 3600001, \"end_ms\": 3600999"))
        check(judge.contains("\"text\": \"Привет \\\"мир\\\"\\nда\""))
        val judgeTwoSpeakers = TranscriptExport.contestJson(listOf(
            TranscriptSegment(0, 100, "speaker-original-B", "раз"),
            TranscriptSegment(100, 200, "speaker-original-A", "два"),
            TranscriptSegment(200, 300, "speaker-original-B", "три")))
        check(Regex("\"speaker_id\": \"speaker_1\"").findAll(judgeTwoSpeakers).count() == 2)
        check(Regex("\"speaker_id\": \"speaker_2\"").findAll(judgeTwoSpeakers).count() == 1)
        check(TranscriptExport.contestJson(emptyList()).contains("\"transcript\": ["))
        check(document.export("txt").contains("[00:00:00.123–00:00:00.456]"))
        val txt = document.export("txt")
        check(txt.startsWith("Стенограмма · 1:00:01 · говорящих: 1\n") && !txt.contains("failed_worker_unknown_speakers"))
        check(txt.contains("Примечание: ошибка\tJNI") && txt.contains("Говорящий 1: Привет"))
        val names = mapOf("Speaker 1" to " Иван ")
        check(document.export("txt", names).contains("] Иван: Привет") && document.export("srt", names).contains("\nИван: Привет"))
        val named = document.export("json", names)
        check(named.contains("\"speaker_id\": \"Speaker 1\", \"speaker_name\": \"Иван\"") && !json.contains("speaker_name"))
        check(document.export("txt", mapOf("Speaker 1" to "  ")).contains("Говорящий 1: Привет"))
        check(document.export("srt").contains("01:00:00,001 --> 01:00:00,999"))
        check(document.export("srt").contains("[перекрытие речи]"))
        check(TranscriptDocument(emptyList(), 1000, provenance).export("json").contains("\"segments\": ["))
        val pinned = provenance.copy(runtimeSha256 = "a".repeat(64))
        check(TranscriptDocument(items, 3601000, pinned).export("json").contains("\"runtime_sha256\": \"${"a".repeat(64)}\""))
        for (bad in listOf("unknown", "", "A".repeat(64), "a".repeat(63))) {
            try { provenance.copy(runtimeSha256 = bad); error("Invalid runtime digest accepted") }
            catch (_: IllegalArgumentException) { }
        }
        try { TranscriptDocument(items, 100, provenance); error("Out-of-audio timestamp accepted") }
        catch (_: IllegalArgumentException) { }
        try { document.export("html"); error("Unknown format accepted") }
        catch (_: IllegalStateException) { }
        writeExportSamples()
        println("PASS transcript document: exact ms, hour/Arabic locale, escaping, provenance, overlap, empty speech, bounds, speaker names")
    } finally { Locale.setDefault(locale) }
}

/** Real exports of this build for tools/verify_transcript_exports.py (CI runs it after :core:runCoreTests). */
private fun writeExportSamples() {
    val segments = listOf(TranscriptSegment(0, 1200, "Speaker 1", "Добрый день, начнём."),
        TranscriptSegment(1300, 2500, "Speaker 2", "Да, я готов: \"план\" на столе."),
        TranscriptSegment(2400, 2600, null, "угу", overlappingSpeech = true),
        TranscriptSegment(2700, 4000, "Speaker 1", "Тогда первый вопрос про котлин и свифте."))
    val document = TranscriptDocument(segments, 4100, TranscriptProvenance("engine", "revision",
        "diarization_boundaries_and_input_windows", "speaker-revision"), listOf("Интервалы фрагментов, не пословное выравнивание."))
    val names = mapOf("Speaker 1" to "Иван", "Speaker 2" to "Мария Петровна")
    val edits = TermDictionary.suggest(segments, BuiltinTerms.ALL)
    check(edits.map { it.replacement } == listOf("Kotlin", "Swift-е"))
    val json = document.export("json", names, edits)
    check(json.contains("\"text\": \"Тогда первый вопрос про котлин и свифте.\", \"text_edited\": \"Тогда первый вопрос про Kotlin и Swift-е.\"") &&
        json.split("text_edited").size == 2)
    check(document.export("txt", names, edits).contains("Иван: Тогда первый вопрос про Kotlin и Swift-е."))
    java.io.File("build/export-samples/contest").apply { mkdirs() }
    java.io.File("build/export-samples/contest/dialogue.json").writeText(document.export("json-contest", names, edits), Charsets.UTF_8)
    for ((name, n, e) in listOf(Triple("plain", emptyMap(), emptyList()), Triple("named", names, emptyList()), Triple("edited", names, edits))) {
        val dir = java.io.File("build/export-samples/$name").apply { mkdirs() }
        for (format in listOf("json", "srt", "txt")) java.io.File(dir, "dialogue.$format").writeText(document.export(format, n, e), Charsets.UTF_8)
    }
}
