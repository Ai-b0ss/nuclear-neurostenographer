package ru.neurostenographer.core

fun testTermDictionary() {
    fun seg(text: String) = TranscriptSegment(0, 1000, "Speaker 1", text)
    val terms = BuiltinTerms.ALL
    fun one(text: String) = TermDictionary.suggest(listOf(seg(text)), terms)

    // Stem with a Russian ending keeps the ending after a hyphen; case of the ending is lowercased.
    check(one("какие-нибудь хаскелевские монады").single().replacement == "Haskell-евские")
    check(one("Пишем на свифте.").single().let { it.original == "свифте" && it.replacement == "Swift-е" })
    check(one("джаваскрипторам объясняют").single().replacement == "JavaScript-орам")
    check(one("Джаваскрипт").single().replacement == "JavaScript")
    // Multi-word variants need plain whitespace between the words.
    check(one("он продакт оунер").single().let { it.original == "продакт оунер" && it.replacement == "Product Owner" })
    check(one("продакт, оунер").isEmpty())
    // Longest variant wins over a shorter prefix: «джаваскрипт» is not «джав…».
    check(one("джава и джаваскрипт").map { it.replacement } == listOf("Java", "JavaScript"))
    // Ambiguous words are proposed but flagged; ordinary words and too-long suffixes are left alone.
    check(one("руби дрова").single().ambiguous)
    check(one("он шёл домой, шел дождь, растёт трава").isEmpty())
    check(one("котлинская котлинскаяяяя").map { it.original } == listOf("котлинская"))
    // Already canonical: nothing to do.
    check(one("Пишу на Kotlin и JavaScript").isEmpty())

    // apply(): exact positions, several edits in one segment, stale edits ignored, raw untouched.
    val raw = listOf(seg("на котлине и свифте пишем"), seg("без терминов"))
    val edits = TermDictionary.suggest(raw, terms)
    check(edits.size == 2)
    val fixed = TermDictionary.apply(raw, edits)
    check(fixed[0].text == "на Kotlin-е и Swift-е пишем" && fixed[1] === raw[1] && raw[0].text == "на котлине и свифте пишем")
    val stale = edits.first().copy(original = "другое")
    check(TermDictionary.apply(raw, listOf(stale)) == raw)
    // User terms work the same way.
    val user = listOf(Term("sherpa-onnx", listOf("шерпа онникс", "шерпа оникс")))
    check(TermDictionary.suggest(listOf(seg("мы используем шерпа оникс")), user).single().replacement == "sherpa-onnx")
    check(TermDictionary.suggest(listOf(seg("нам помогал шерпа")), user).isEmpty())
    for (bad in listOf<() -> Unit>({ Term(" ", listOf("x")) }, { Term("X", emptyList()) }, { Term("X", listOf("Заглавная")) },
            { Term("X", listOf("a*b")) })) {
        try { bad(); error("Invalid term accepted") } catch (_: IllegalArgumentException) { }
    }
    println("PASS term dictionary: stems+endings, multi-word, longest match, ambiguous flag, common-word guards, apply/stale")
}
