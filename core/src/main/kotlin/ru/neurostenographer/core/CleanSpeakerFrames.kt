package ru.neurostenographer.core

/**
 * Select complete frames covered by exactly one attribution-eligible turn.
 * ALL turns block overlapped samples, including low-confidence/ineligible turns.
 * A fragmentary or malformed timeline produces no identity evidence.
 */
object CleanSpeakerFrames {
    data class Selection(val speakerIds: List<String>, val owners: IntArray)

    /**
     * Two non-overlapping, time-separated evidence samples of one local speaker.
     * A single prefix must NOT authorize assigning one global identity to the
     * rest of the five-minute block. Missing second evidence => no link.
     */
    data class SeparatedSamples(val early: IntArray, val late: IntArray)

    fun separate(owners: IntArray, speakerIndex: Int,
                 minFramesPerSample: Int = 75,
                 maxFramesPerSample: Int = 200): SeparatedSamples? {
        require(speakerIndex >= 0 && minFramesPerSample > 0 &&
            maxFramesPerSample >= minFramesPerSample && owners.size <= 30_000)
        val active = owners.indices.filter { owners[it] == speakerIndex }
        if (active.size < minFramesPerSample * 2) return null
        val middle = active.size / 2
        val first = active.take(middle).take(maxFramesPerSample).toIntArray()
        val second = active.drop(middle).takeLast(maxFramesPerSample).toIntArray()
        if (first.size < minFramesPerSample || second.size < minFramesPerSample ||
            first.last() >= second.first()) return null
        return SeparatedSamples(first, second)
    }

    fun select(turns: List<SpeakerTurn>, frames: Int,
               durationMs: Long, hopMs: Int = 40): Selection {
        require(frames >= 0 && frames <= 30_000 && hopMs in 10..200 && durationMs >= 0)
        val ids = turns.filter { it.attributionEligible }.map { it.speakerId }.distinct()
        if (ids.isEmpty() || ids.size > 8) return Selection(emptyList(), IntArray(frames) { -1 })
        val empty = Selection(emptyList(), IntArray(frames) { -1 })
        if (turns.any { it.endMs > durationMs || it.startMs < 0 ||
                    it.endMs <= it.startMs }) return empty
        val blockers = IntArray(frames)
        for (turn in turns) {
            // Even an ineligible short or competing turn contaminates any
            // intersecting 40ms frame. Round outward, not inward.
            val first = (turn.startMs / hopMs).toInt().coerceIn(0, frames)
            val after = ((turn.endMs + hopMs - 1) / hopMs).toInt().coerceIn(0, frames)
            for (i in first until after) {
                if (blockers[i] < 2) blockers[i]++
            }
        }
        val index = ids.withIndex().associate { it.value to it.index }
        val owners = IntArray(frames) { -1 }
        for (turn in turns) {
            if (!turn.attributionEligible) continue
            val id = index[turn.speakerId] ?: continue
            val start = ((turn.startMs + hopMs - 1) / hopMs).toInt().coerceIn(0, frames)
            val after = (turn.endMs / hopMs).toInt().coerceIn(0, frames)
            for (i in start until after) {
                if (blockers[i] == 1) owners[i] = id
            }
        }
        return Selection(ids, owners)
    }
}
