package ru.neurostenographer.core

/** Pure overlap scheduling and STNO masks shared by host tests and Android integration.
 * Identity comes solely from Nemotron's turn labels; never assign an inferred person.
 */
data class FddtRegion(val startMs: Long, val endMs: Long, val speakers: List<String>) {
    init { require(startMs >= 0 && endMs > startMs && speakers.size >= 2) }
}

object FddtOverlapPlan {
    /** Replace only actual overlap. Context belongs to the inference window, not
     * the replacement interval: clean parts of long turns stay on A3.
     */
    fun regions(turns: List<SpeakerTurn>, audioMs: Long, wholeTurns: Boolean = false): List<FddtRegion> {
        if (audioMs < 1000) return emptyList()
        val known = turns.filter { it.speakerId != "Unknown" && it.endMs <= audioMs }
            .sortedWith(compareBy<SpeakerTurn> { it.startMs }.thenBy { it.endMs })
        if (known.size < 2) return emptyList()
        val intersections = mutableListOf<Pair<Long,Long>>()
        val affected = BooleanArray(known.size)
        for (i in known.indices) {
            for (j in i + 1 until known.size) {
                if (known[j].startMs >= known[i].endMs) break
                if (known[i].speakerId != known[j].speakerId) {
                    val overlap = minOf(known[i].endMs, known[j].endMs) -
                        maxOf(known[i].startMs, known[j].startMs)
                    if (overlap >= 160L) {
                        intersections += maxOf(known[i].startMs,known[j].startMs) to minOf(known[i].endMs,known[j].endMs)
                        affected[i] = true; affected[j] = true
                    }
                }
            }
        }
        if (intersections.isEmpty()) return emptyList()
        val intervals = if (wholeTurns) known.filterIndexed { i,_ -> affected[i] }.map { it.startMs to it.endMs }
            else intersections
        val components = mutableListOf<Pair<Long, Long>>()
        for ((start,end) in intervals.sortedBy { it.first }) {
            val last = components.lastOrNull()
            if (last != null && start <= last.second + if (wholeTurns) 100L else 0L) {
                components[components.lastIndex] = last.first to maxOf(last.second,end)
            } else components += start to end
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
        val windowEndMs = startMs + samples * 1000L / 16000L
        val rasterized = turns.filter { it.startMs < windowEndMs && it.endMs > startMs }.map {
            Triple(((maxOf(it.startMs,startMs)-startMs)/40L).toInt(),
                ((minOf(it.endMs,windowEndMs)-startMs+39L)/40L).toInt(), it.speakerId)
        }
        for (i in 0 until frames) {
            var target = false; var other = false
            for ((first,last,id) in rasterized) {
                // Match Python stno_mask: floor(start*25):ceil(end*25), after
                // clipping turns to this audio window. Point sampling shifts onsets.
                if (i >= first && i < last) {
                    if (id == speaker) target = true else other = true
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

    /** A long foreground voice must never compensate a suppressed quiet voice.
     * Unknown mixture words remain a regional check, never a fabricated per-person reference.
     */
    fun canReplace(base: List<TranscriptSegment>, candidates: Map<String,String>, speakers: List<String>): Boolean {
        fun count(text: String) = text.split(Regex("\\s+")).count(String::isNotBlank)
        if (!canReplace(base.sumOf { count(it.text) }, candidates, speakers)) return false
        for (speaker in speakers) {
            val before = base.filter { it.speakerId == speaker }.sumOf { count(it.text) }
            val after = count(candidates[speaker].orEmpty())
            if (before > 0 && (after < before * 0.5 || after > maxOf(8, before * 3))) return false
        }
        return true
    }

    /** Half-open ownership keeps a word in exactly one adjacent inference region. */
    fun owns(region: FddtRegion, word: RecognizedWord): Boolean =
        word.startMs >= region.startMs && word.startMs < region.endMs

    /** Preserve A3 words, punctuation, order and timing. Only an ambiguous single
     * word with matching timed FDDT evidence from exactly one voice is attributed.
     * Common words seen in both voices remain unknown.
     */
    fun refineAttribution(base: List<TranscriptSegment>, evidence: List<TranscriptSegment>): List<TranscriptSegment> {
        fun normalized(text: String) = text.lowercase(java.util.Locale.ROOT).replace('ё','е')
            .split(Regex("[^\\p{L}\\p{N}]+")).filter(String::isNotBlank)
        val indexed = evidence.filter { it.speakerId != null }
            .map { it to normalized(it.text).toSet() }
        return base.map { word ->
            if (word.speakerId != null || !word.overlappingSpeech) return@map word
            val tokens = normalized(word.text)
            if (tokens.size != 1) return@map word
            val voices = indexed.asSequence().filter { (candidate, words) ->
                tokens.single() in words && word.startMs < candidate.endMs+200L &&
                    word.endMs > candidate.startMs-200L
            }.mapNotNull { it.first.speakerId }.distinct().toList()
            if (voices.size == 1) word.copy(speakerId=voices.single(),attributionReliable=false) else word
        }
    }
}
