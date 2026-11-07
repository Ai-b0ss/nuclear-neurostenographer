package ru.neurostenographer.core

/** Actual PCM RMS, displayed over a -60..0 dBFS range. No time-driven synthetic activity. */
object VoiceLevel {
    fun measure(samples: ShortArray, count: Int = samples.size): Float {
        require(count in 0..samples.size)
        if (count == 0) return 0f
        var squares = 0.0
        for (i in 0 until count) { val x = samples[i] / 32768.0; squares += x * x }
        val rms = kotlin.math.sqrt(squares / count)
        if (rms <= 0.001) return 0f
        return ((20 * kotlin.math.log10(rms) + 60) / 60).toFloat().coerceIn(0f, 1f)
    }
}
