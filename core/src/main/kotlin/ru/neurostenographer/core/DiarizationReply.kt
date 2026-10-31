package ru.neurostenographer.core

/** Validate the worker boundary before any inferred speaker/window reaches ASR.
 * Empty output is valid silence, never an instruction to invent speech.
 */
object DiarizationReply {
    const val MAX_ITEMS = 2000
    data class Validated(val turns: List<SpeakerTurn>, val windows: List<AudioWindow>)

    fun validate(audioMs: Long, starts: LongArray, ends: LongArray,
                 speakers: List<String>, eligible: BooleanArray,
                 windowStarts: LongArray, windowEnds: LongArray,
                 loadMs: Long, processMs: Long): Validated {
        require(audioMs in 100..(PcmWav.MAX_SECONDS * 1000L))
        require(starts.size <= MAX_ITEMS && windowStarts.size <= MAX_ITEMS)
        require(starts.size == ends.size && starts.size == speakers.size && starts.size == eligible.size)
        require(windowStarts.size == windowEnds.size && loadMs >= 0 && processMs >= 0)
        val label = Regex("Speaker [1-9][0-9]{0,3}")
        val turns = starts.indices.map { i ->
            require(starts[i] >= 0 && starts[i] < ends[i] && ends[i] <= audioMs)
            require(speakers[i] == "Unknown" || label.matches(speakers[i]))
            require(!eligible[i] || (speakers[i] != "Unknown" && ends[i] - starts[i] >= 300))
            SpeakerTurn(starts[i], ends[i], speakers[i], eligible[i])
        }
        require(turns.zipWithNext().all { (a, b) -> a.startMs <= b.startMs })
        val windows = windowStarts.indices.map { i ->
            require(windowStarts[i] >= 0 && windowStarts[i] < windowEnds[i] && windowEnds[i] <= audioMs &&
                windowEnds[i] - windowStarts[i] in 100..20_000)
            AudioWindow(windowStarts[i], windowEnds[i])
        }
        require(windows.zipWithNext().all { (a, b) -> a.endMs <= b.startMs })
        // The same partition policy is used inside the worker. In particular a
        // missing/extra window cannot silently omit speech or decode a silence gap.
        val expected = DiarizationTimeline.windows(turns, audioMs).filter { w ->
            turns.any { it.startMs <= w.startMs && it.endMs >= w.endMs }
        }
        require(windows == expected) { "Worker speech windows disagree with turns" }
        return Validated(turns, windows)
    }
}
