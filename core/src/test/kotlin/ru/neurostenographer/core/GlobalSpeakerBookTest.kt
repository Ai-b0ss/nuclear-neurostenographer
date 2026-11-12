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
    // An adapting centroid must NEVER be allowed to drift away from the
    // first enrollment voice. The old implementation accepted repeated
    // small rotations until it linked nearly orthogonal speakers.
    val driftBook = GlobalSpeakerBook()
    check(driftBook.link(listOf(p("enroll", 1f, 0f)))["enroll"] == "Speaker 1")
    for (angle in 4..100 step 4) {
        val rad = Math.toRadians(angle.toDouble())
        val probe = p("probe", kotlin.math.cos(rad).toFloat(),
                      kotlin.math.sin(rad).toFloat())
        val assigned = driftBook.link(listOf(probe))["probe"]
        if (angle >= 36) {
            check(assigned != "Speaker 1") {
                "Unanchored centroid drifted identity to angle " + angle
            }
        }
    }
    // The immutable anchor does NOT stop ordinary small speaker variation.
    val stableBook = GlobalSpeakerBook()
    check(stableBook.link(listOf(p("a", 1f, 0f)))["a"] == "Speaker 1")
    check(stableBook.link(listOf(p("b", 0.985f, 0.17f)))["b"] == "Speaker 1")
    check(stableBook.link(listOf(p("c", 0.98f, 0.19f)))["c"] == "Speaker 1")
    // Inconsistent temporal excerpts can ONLY reuse the same independently verified old anchor.
    fun pair(id: String, early: FloatArray, late: FloatArray) = VoicePrint(id,
        requireNotNull(VoicePrintAgreement.mergeIfConsistent(early, late, minCosine = 0.0)),
        6000, early, late, 3000, 3000)
    fun at(degrees: Double) = floatArrayOf(kotlin.math.cos(Math.toRadians(degrees)).toFloat(),
        kotlin.math.sin(Math.toRadians(degrees)).toFloat(), 0f)
    val mixedDimensions = GlobalSpeakerBook()
    check(mixedDimensions.link(listOf(p("two",1f,0f),p("three",1f,0f,0f))).isEmpty())
    check(mixedDimensions.size() == 0)
    val rescueBook = GlobalSpeakerBook()
    rescueBook.link(listOf(p("anchor", 1f, 0f, 0f)))
    repeat(40) { check(rescueBook.link(listOf(pair("return", at(30.0), at(-20.0))))["return"] == "Speaker 1") }
    check(rescueBook.size() == 1)
    // Reuse-only evidence must not adapt the centroid toward the asymmetric pair.
    check(rescueBook.link(listOf(VoicePrint("edge", at(-30.0), 4000)))["edge"] == "Speaker 1")
    check(rescueBook.link(listOf(pair("one_bad_half",at(0.0),at(50.0)))).isEmpty())
    val pairedAmbiguous = GlobalSpeakerBook()
    pairedAmbiguous.link(listOf(p("near_a",1f,0f,0f),p("near_b",0.999f,0f,0.04f)))
    check(pairedAmbiguous.link(listOf(pair("unclear",at(30.0),at(-20.0)))).isEmpty())
    check(pairedAmbiguous.size() == 2)
    val unknownPair = GlobalSpeakerBook()
    check(unknownPair.link(listOf(pair("unknown", at(30.0), at(-20.0)))).isEmpty())
    check(unknownPair.size() == 0)
    val switched = GlobalSpeakerBook()
    switched.link(listOf(p("a", 1f, 0f, 0f), p("b", 0f, 1f, 0f)))
    check(switched.link(listOf(pair("mixed", floatArrayOf(1f,0f,0f), floatArrayOf(0f,1f,0f)))).isEmpty())
    check(switched.size() == 2)
    val collisionBook = GlobalSpeakerBook()
    collisionBook.link(listOf(p("anchor", 1f,0f,0f)))
    check(collisionBook.link(listOf(pair("x", at(30.0), at(-20.0)), pair("y",at(30.0),at(-20.0)))).isEmpty())
    check(collisionBook.size() == 1)
    val sameBlock = GlobalSpeakerBook()
    val simultaneous = sameBlock.link(listOf(p("fresh",1f,0f,0f), pair("unproven",at(30.0),at(-20.0))))
    check(simultaneous.keys == setOf("fresh"))
    val malformed = pair("bad",at(30.0),at(-20.0))
    check(collisionBook.link(listOf(malformed.copy(lateEmbedding=null))).isEmpty())
    check(collisionBook.link(listOf(malformed.copy(earlySpeechMs=2999,cleanSpeechMs=5999))).isEmpty())
    check(collisionBook.link(listOf(malformed.copy(earlyEmbedding=floatArrayOf(Float.NaN,0f,0f)))).isEmpty())
    check(collisionBook.link(listOf(malformed.copy(embedding=floatArrayOf(0f,1f,0f)))).isEmpty())
    fun decode(version: Int = 2, early: FloatArray? = malformed.earlyEmbedding,
               late: FloatArray? = malformed.lateEmbedding, earlyMs: LongArray? = longArrayOf(3000)) =
        VoicePrintReply.decode(version,listOf("bad"),longArrayOf(6000),malformed.embedding,
            early,late,earlyMs,longArrayOf(3000),setOf("bad"),6000,3)
    check(decode().size == 1)
    check(decode(version=1).isEmpty())
    check(decode(early=null).isEmpty())
    check(decode(late=null).isEmpty())
    check(decode(earlyMs=null).isEmpty())
    check(decode(early=floatArrayOf(1f)).isEmpty())
    check(decode(earlyMs=longArrayOf(2999)).isEmpty())
    verifyDualAnchorReplayIfAvailable()
    println("PASS dual-anchor: paired reuse, no unproven enrollment, slot-switch rejection, collision, immutable centroid, strict IPC")
    println("PASS global speaker book: A-B-A, swapped slots, ambiguity, collision, overlap, invalid input")
}
