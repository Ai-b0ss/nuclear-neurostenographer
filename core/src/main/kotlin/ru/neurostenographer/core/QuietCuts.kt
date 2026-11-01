package ru.neurostenographer.core

/** Moves forced 20-second cuts back to the quietest nearby moment so they rarely
 * land inside a word. Input and output windows cover the same audio.
 */
object QuietCuts {
    private const val MAX_WINDOW_MS = 20_000L
    private const val SEARCH_MS = 2_000L
    private const val FRAME_MS = 30L
    private const val STEP_MS = 10L

    fun refine(windows: List<AudioWindow>, samples: FloatArray, sampleRate: Int = 16000): List<AudioWindow> {
        val result = windows.toMutableList()
        for (i in 0 until result.lastIndex) {
            val current = result[i]
            val next = result[i + 1]
            if (windows[i].endMs - windows[i].startMs != MAX_WINDOW_MS || current.endMs != next.startMs) continue
            // A following forced cut can still move back, a final piece cannot.
            val nextIsForced = next.endMs - next.startMs == MAX_WINDOW_MS && i + 2 <= windows.lastIndex &&
                windows[i + 2].startMs == next.endMs
            var lowest = current.endMs - SEARCH_MS
            if (!nextIsForced) lowest = maxOf(lowest, next.endMs - MAX_WINDOW_MS)
            val cut = quietest(samples, sampleRate, lowest, current.endMs)
            result[i] = AudioWindow(current.startMs, cut)
            result[i + 1] = AudioWindow(cut, next.endMs)
        }
        return result
    }

    private fun quietest(samples: FloatArray, sampleRate: Int, fromMs: Long, toMs: Long): Long {
        var best = toMs
        var bestEnergy = Double.MAX_VALUE
        var at = toMs
        while (at >= fromMs) {
            val center = at * sampleRate / 1000
            val half = FRAME_MS * sampleRate / 2000
            val start = maxOf(0L, center - half).toInt()
            val end = minOf(samples.size.toLong(), center + half).toInt()
            var energy = 0.0
            for (index in start until end) energy += samples[index] * samples[index]
            // Strict comparison keeps the original cut when the audio is uniform.
            if (end > start && energy < bestEnergy) {
                bestEnergy = energy
                best = at
            }
            at -= STEP_MS
        }
        return best
    }
}
