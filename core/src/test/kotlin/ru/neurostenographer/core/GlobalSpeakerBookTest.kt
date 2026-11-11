package ru.neurostenographer.core

fun testGlobalSpeakerBook() {
    fun p(id: String, vararg values: Float, ms: Long = 4000) = VoicePrint(id, values, ms)
    val book = GlobalSpeakerBook()
    val first = book.link(listOf(p("Speaker 1", 1f, 0f, 0f), p("Speaker 2", 0f, 1f, 0f)))
    check(first == mapOf("Speaker 1" to "Speaker 1", "Speaker 2" to "Speaker 2"))
    // Same people, reversed per-window C2 slot numbers.
    val second = book.link(listOf(
        p("Speaker 1", 0.02f, 0.999f, 0f),
        p("Speaker 2", 0.995f, 0.02f, 0f),
        p("Speaker 3", 0f, 0f, 1f)))
    check(second == mapOf("Speaker 1" to "Speaker 2", "Speaker 2" to "Speaker 1",
        "Speaker 3" to "Speaker 3")) { second.toString() }
    check(book.size() == 3)
    val shifted = LocalSpeakerScope.shift(TranscriptSegment(30, 100, "Speaker 1", "привет"),
        300_000, 1, second)
    check(shifted.speakerId == "Speaker 2" && shifted.startMs == 300_030L)
    val overlap = LocalSpeakerScope.shift(
        TranscriptSegment(100, 200, null, "оба", true, false, listOf("Speaker 1", "Speaker 2")),
        300_000, 1, second)
    check(overlap.speakerId == null && overlap.overlapSpeakers == listOf("Speaker 2", "Speaker 1"))
    val invalid = book.link(listOf(p("short", 1f, 0f, 0f, ms = 400),
        p("bad", Float.NaN, 0f, 0f), p("silent", 0f, 0f, 0f)))
    check(invalid.isEmpty() && book.size() == 3)
    check(LocalSpeakerScope.shift(TranscriptSegment(0, 100, "short", "да"), 600_000, 2,
        invalid).speakerId == "Block 3 / short")
    // Two distinct local speakers cannot both map to one known global speaker.
    val conflict = book.link(listOf(p("x", 1f, 0f, 0f), p("y", 1f, 0f, 0f)))
    check(conflict.size == 2 && conflict["x"] != conflict["y"])
    check(conflict.values.none { it == "Speaker 1" })
    val ambiguous = GlobalSpeakerBook(minCosine = 0.65, minMargin = 0.2)
    ambiguous.link(listOf(p("a", 1f, 0f), p("b", 0f, 1f)))
    check(ambiguous.link(listOf(p("c", 0.75f, 0.66f)))["c"] == "Speaker 3")
    val arr = floatArrayOf(1f, 0f, 0f)
    book.link(listOf(VoicePrint("n", arr, 4000)))
    check(arr.contentEquals(floatArrayOf(1f, 0f, 0f)))
    check(runCatching { book.link(listOf(p("dup", 1f, 0f), p("dup", 0f, 1f))) }.isFailure)
    check(runCatching { book.link((0..8).map { p("id$it", 1f, 0f) }) }.isFailure)
    println("PASS global speaker book: A-B-A, swapped slots, ambiguity, collision, overlap, invalid input")
}
