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
        check(document.export("txt").contains("failed_worker_unknown_speakers"))
        check(document.export("srt").contains("01:00:00,001 --> 01:00:00,999"))
        check(document.export("srt").contains("[перекрытие речи]"))
        check(TranscriptDocument(emptyList(), 1000, provenance).export("json").contains("\"segments\": ["))
        try { TranscriptDocument(items, 100, provenance); error("Out-of-audio timestamp accepted") }
        catch (_: IllegalArgumentException) { }
        try { document.export("html"); error("Unknown format accepted") }
        catch (_: IllegalStateException) { }
        println("PASS transcript document: exact ms, hour/Arabic locale, escaping, provenance, overlap, empty speech, bounds")
    } finally { Locale.setDefault(locale) }
}
