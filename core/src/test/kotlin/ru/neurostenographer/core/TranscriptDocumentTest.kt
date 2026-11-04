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
        TranscriptSegment(2700, 4000, "Speaker 1", "Тогда первый вопрос."))
    val document = TranscriptDocument(segments, 4100, TranscriptProvenance("engine", "revision",
        "diarization_boundaries_and_input_windows", "speaker-revision"), listOf("Интервалы фрагментов, не пословное выравнивание."))
    for ((name, names) in listOf("plain" to emptyMap(), "named" to mapOf("Speaker 1" to "Иван", "Speaker 2" to "Мария Петровна"))) {
        val dir = java.io.File("build/export-samples/$name").apply { mkdirs() }
        for (format in listOf("json", "srt", "txt")) java.io.File(dir, "dialogue.$format").writeText(document.export(format, names), Charsets.UTF_8)
    }
}
