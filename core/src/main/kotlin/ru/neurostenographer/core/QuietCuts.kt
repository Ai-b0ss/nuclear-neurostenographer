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
        val moved = windows.toMutableList()
        for (i in 0 until windows.lastIndex) {
            val window = windows[i]
            if (window.endMs - window.startMs != MAX_WINDOW_MS || window.endMs != windows[i + 1].startMs) continue
            val cut = quietest(samples, sampleRate, window.endMs - SEARCH_MS, window.endMs)
            moved[i] = moved[i].copy(endMs = cut)
            moved[i + 1] = moved[i + 1].copy(startMs = cut)
        }
        // A window that grew past the model limit is split once; it stays under 22 s + 2 s search.
        return moved.flatMap { window ->
            if (window.endMs - window.startMs <= MAX_WINDOW_MS) listOf(window)
            else {
                val middle = (window.startMs + window.endMs) / 2
                val cut = quietest(samples, sampleRate, middle - SEARCH_MS, middle)
                listOf(AudioWindow(window.startMs, cut), AudioWindow(cut, window.endMs))
            }
        }
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
