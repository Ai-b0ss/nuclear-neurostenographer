package ru.neurostenographer.core

import java.util.Locale

/**
 * B0 from docs/CONTEXTUAL_ASR_DECISION_2026-11-04.md: a reversible spelling dictionary applied AFTER ASR.
 * It never touches the decoder or audio, never inserts or deletes words: it only proposes to rewrite a word (or a short
 * run of adjacent words) that ASR wrote in Cyrillic, e.g. «джаваскрипт» → «JavaScript», «хаскелевские» → «Haskell-евские».
 * Proposals are shown as «было → стало»; the raw ASR text is kept, accepted edits are stored separately.
 *
 * A variant is lowercase words separated by spaces; a trailing `*` on the last word is a stem that also matches up to
 * [MAX_SUFFIX] more Cyrillic letters (Russian endings), which are kept after a hyphen: «свифте» → «Swift-е».
 * `ambiguous` terms also mean an ordinary Russian word («питон», «руби») and are never pre-selected.
 * A canonical form ending in a Cyrillic letter takes the ending without a hyphen («хокотона» → «хакатона», «твеллы» → «ТВЭЛы»);
 * a canonical ending in `*` is itself a stem: «диаризац*» + «ии» → «диаризации».
 */
data class Term(val canonical: String, val variants: List<String>, val ambiguous: Boolean = false) {
    init {
        require(canonical.isNotBlank() && canonical.none { it == '\n' } && variants.isNotEmpty())
        require(!canonical.dropLast(1).contains('*') && canonical.removeSuffix("*").isNotBlank())
        require(variants.all { v -> v.isNotBlank() && v == v.lowercase(Locale.ROOT) && !v.dropLast(1).contains('*') })
    }
}

/** Proposal to replace [original] = segment text [start, end) with [replacement]. */
data class TermEdit(val segment: Int, val start: Int, val end: Int, val original: String, val replacement: String,
                    val ambiguous: Boolean = false) {
    init { require(segment >= 0 && start >= 0 && end > start && replacement.isNotBlank()) }
}

object TermDictionary {
    const val MAX_SUFFIX = 6
    private val WORD = Regex("[\\p{L}\\p{N}]+(?:-[\\p{L}\\p{N}]+)*")
    private val CYRILLIC = Regex("[а-яё]+")

    private fun norm(s: String) = s.lowercase(Locale.ROOT).replace('ё', 'е')

    private class Pattern(val term: Term, val words: List<String>, val stem: Boolean)

    private fun patterns(terms: List<Term>): List<Pattern> = terms.flatMap { t ->
        t.variants.map { v ->
            val ws = norm(v).trim().split(Regex("\\s+"))
            val stem = ws.last().endsWith("*")
            Pattern(t, if (stem) ws.dropLast(1) + ws.last().dropLast(1) else ws, stem)
        }
    }.sortedWith(compareByDescending<Pattern> { it.words.size }.thenByDescending { it.words.sumOf(String::length) })

    /** Non-overlapping proposals, left to right, longest variant first. Text already equal to the canonical form is skipped. */
    fun suggest(segments: List<TranscriptSegment>, terms: List<Term>): List<TermEdit> {
        if (terms.isEmpty()) return emptyList()
        val all = patterns(terms)
        val out = mutableListOf<TermEdit>()
        segments.forEachIndexed { index, segment ->
            val text = segment.text
            val words = WORD.findAll(text).toList()
            var i = 0
            while (i < words.size) {
                var consumed = 1
                for (p in all) {
                    val n = p.words.size
                    if (i + n > words.size) continue
                    // Words of a multi-word variant must be separated by whitespace only (no punctuation in between).
                    if ((1 until n).any { k -> text.substring(words[i + k - 1].range.last + 1, words[i + k].range.first).isNotBlank() }) continue
                    if ((0 until n - 1).any { k -> norm(words[i + k].value) != p.words[k] }) continue
                    val last = norm(words[i + n - 1].value)
                    val head = p.words.last()
                    val suffix = when {
                        last == head -> ""
                        p.stem && last.startsWith(head) && last.length - head.length <= MAX_SUFFIX &&
                            CYRILLIC.matches(last.substring(head.length)) -> words[i + n - 1].value.substring(head.length)
                        else -> null
                    } ?: continue
                    val start = words[i].range.first
                    val end = words[i + n - 1].range.last + 1
                    // A lowercase canonical keeps the capital the ASR gave it at a sentence start: «Хокотон» → «Хакатон».
                    val base = p.term.canonical.removeSuffix("*").let { c ->
                        if (c.first().isLowerCase() && words[i].value.first().isUpperCase()) c.replaceFirstChar { it.uppercaseChar() } else c }
                    val joiner = if (CYRILLIC.matches(norm(base.last().toString()))) "" else "-"
                    val replacement = base + if (suffix.isEmpty()) "" else joiner + suffix.lowercase(Locale.ROOT)
                    if (text.substring(start, end) != replacement)
                        out += TermEdit(index, start, end, text.substring(start, end), replacement, p.term.ambiguous)
                    consumed = n
                    break
                }
                i += consumed
            }
        }
        return out
    }

    /** Applies accepted edits to a copy of the segments; edits that no longer match the raw text are ignored. */
    fun apply(segments: List<TranscriptSegment>, edits: List<TermEdit>): List<TranscriptSegment> {
        val bySegment = edits.groupBy { it.segment }
        return segments.mapIndexed { index, s ->
            val mine = bySegment[index].orEmpty().sortedByDescending { it.start }
            var text = s.text
            var limit = text.length
            for (e in mine) {
                if (e.end > limit || e.end > text.length || text.substring(e.start, e.end) != e.original) continue
                text = text.substring(0, e.start) + e.replacement + text.substring(e.end)
                limit = e.start
            }
            if (text == s.text) s else s.copy(text = text)
        }
    }
}
