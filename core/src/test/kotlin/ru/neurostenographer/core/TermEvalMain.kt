package ru.neurostenographer.core

import java.io.File

/** Host evaluation hook for tools/term_dictionary/eval.py: applies BuiltinTerms with the SAME code the app uses.
 * Input TSV: id<TAB>text. Output TSV: id<TAB>accept_all<TAB>accept_unambiguous<TAB>edits<TAB>ambiguous_edits<TAB>pairs
 * where pairs = "original=>replacement" joined by " | ". */
object TermEvalMain {
    @JvmStatic fun main(args: Array<String>) {
        val out = File(args[1]).bufferedWriter(Charsets.UTF_8)
        File(args[0]).readLines(Charsets.UTF_8).filter { it.isNotBlank() }.forEach { line ->
            val (id, text) = line.split('\t', limit = 2)
            val segment = listOf(TranscriptSegment(0, 1, null, text))
            val edits = TermDictionary.suggest(segment, BuiltinTerms.ALL)
            val all = TermDictionary.apply(segment, edits).single().text
            val safe = TermDictionary.apply(segment, edits.filter { !it.ambiguous }).single().text
            out.write(listOf(id, all, safe, edits.size, edits.count { it.ambiguous },
                edits.joinToString(" | ") { "${it.original}=>${it.replacement}" }).joinToString("\t") + "\n")
        }
        out.close()
    }
}
