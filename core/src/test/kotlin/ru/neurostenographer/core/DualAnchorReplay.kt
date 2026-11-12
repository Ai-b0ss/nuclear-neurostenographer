package ru.neurostenographer.core
import java.io.File
/** Optional local real-model parity harness; no embeddings are printed or committed. */
fun verifyDualAnchorReplayIfAvailable() {
    val location = System.getenv("NEURO_DUAL_ANCHOR_REPLAY") ?: return
    val directory = File(location)
    var book = GlobalSpeakerBook()
    var dataset = ""
    var clip = ""
    val profiles = mutableListOf<VoicePrint>()
    val actual = mutableListOf<String>()
    var blocks = 0
    File(directory,"private-replay.tsv").forEachLine { line ->
        val fields = line.split('\t')
        when (fields[0]) {
            "B" -> {
                check(profiles.isEmpty())
                if (dataset != fields[1]) { dataset=fields[1];book=GlobalSpeakerBook() }
                clip=fields[2]
            }
            "P" -> {
                fun vector(index: Int) = fields[index].split(',').map { it.toFloat() }.toFloatArray()
                val earlyMs=fields[2].toLong();val lateMs=fields[3].toLong()
                profiles += VoicePrint(fields[1],vector(4),earlyMs+lateMs,vector(5),vector(6),earlyMs,lateMs)
            }
            "E" -> {
                book.link(profiles).forEach { (local,id) -> actual += listOf(dataset,clip,local,id).joinToString("\t") }
                profiles.clear();blocks++
            }
            else -> error("Invalid local replay")
        }
    }
    val expected=File(directory,"expected-links.tsv").readLines().filter { it.isNotBlank() }
    check(actual.sorted()==expected.sorted()) { "Python/Kotlin global links diverged" }
    println("PASS real-model dual-anchor parity: "+blocks+" blocks, "+actual.size+" identical assignments")
}
