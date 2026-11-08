package ru.neurostenographer.core

/** Pure overlap scheduling and STNO masks shared by host tests and Android integration.
 * Identity comes solely from Nemotron's turn labels; never assign an inferred person.
 */
data class FddtRegion(val startMs: Long, val endMs: Long, val speakers: List<String>) {
    init { require(startMs >= 0 && endMs > startMs && speakers.size >= 2) }
}

object FddtOverlapPlan {
    /** The whole turn affected by overlap is processed, not only the literal intersection.
     * This mirrors Ruzanna's hybrid transcribe_hybrid and protects word boundaries.
     */
    fun regions(turns: List<SpeakerTurn>, audioMs: Long): List<FddtRegion> {
        if (audioMs < 1000) return emptyList()
        val known = turns.filter { it.speakerId != "Unknown" && it.endMs <= audioMs }
            .sortedWith(compareBy<SpeakerTurn> { it.startMs }.thenBy { it.endMs })
        if (known.size < 2) return emptyList()
        val affected = BooleanArray(known.size)
        for (i in known.indices) {
            for (j in i + 1 until known.size) {
                if (known[j].startMs >= known[i].endMs) break
                if (known[i].speakerId != known[j].speakerId) {
                    val overlap = minOf(known[i].endMs, known[j].endMs) -
                        maxOf(known[i].startMs, known[j].startMs)
                    if (overlap >= 160L) { affected[i] = true; affected[j] = true }
                }
            }
        }
        val active = known.filterIndexed { i, _ -> affected[i] }
        if (active.isEmpty()) return emptyList()
        val components = mutableListOf<Pair<Long, Long>>()
        for (t in active) {
            val last = components.lastOrNull()
            if (last != null && t.startMs <= last.second + 100L) {
                components[components.lastIndex] = last.first to maxOf(last.second,t.endMs)
            } else components += t.startMs to t.endMs
        }
        return components.flatMap { (start,end) ->
            val parts = mutableListOf<FddtRegion>()
            var at = start
            while (at < end) {
                val stop = minOf(end,at + 20_000)
                val speakers = known.asSequence()
                    .filter { it.startMs < stop && it.endMs > at }
                    .map { it.speakerId }.distinct().sorted().toList()
                if (speakers.size >= 2) parts += FddtRegion(at,stop,speakers)
                at = stop
            }
            parts
        }
    }

    fun frameCount(samples: Int): Int {
        require(samples in 16_000..(25*16_000))
        return (samples + 639) / 640 + 1
    }

    /** Float mask [4,M] row-major; STNO 0 silence, 1 target, 2 other, 3 overlap.
     * "Unknown" voice contributes only to the non-target category.
     */
    fun mask(turns: List<SpeakerTurn>, speaker: String, startMs: Long, samples: Int): FloatArray {
        require(speaker.isNotBlank() && startMs >= 0)
        val frames = frameCount(samples)
        val out = FloatArray(4*frames)
        for (i in 0 until frames) {
            val at = startMs + 40L*i
            var target = false; var other = false
            for (turn in turns) {
                if (at >= turn.startMs && at < turn.endMs) {
                    if (turn.speakerId == speaker) target = true else other = true
                    if (target && other) break
                }
            }
            val state = if (target) { if (other) 3 else 1 } else { if (other) 2 else 0 }
            out[state*frames+i] = 1f
        }
        return out
    }

    fun decodePieces(pieces: List<String>): String =
        pieces.joinToString("").replace('\u2581',' ').trim().replace(Regex("\\s+")," ")

    /** Reject an obviously emptied or wildly inflated hypothesis, without replacing
     * a missing quiet speaker by text incorrectly attributed to somebody else.
     */
    fun canReplace(baseWords: Int, candidates: Map<String,String>, speakers: List<String>): Boolean {
        if (speakers.size < 2 || speakers.any { candidates[it].isNullOrBlank() }) return false
        val count = candidates.values.sumOf { it.split(Regex("\\s+")).count(String::isNotBlank) }
        if (count < 2) return false
        if (baseWords > 0 && count < baseWords*0.5) return false
        if (baseWords > 0 && count > maxOf(8,baseWords*3)) return false
        return true
    }
}
