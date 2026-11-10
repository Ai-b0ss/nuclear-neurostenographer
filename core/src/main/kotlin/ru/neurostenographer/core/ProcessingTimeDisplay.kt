package ru.neurostenographer.core

/** Small, readable ETA, not a pretend second-accurate measurement. */
object ProcessingTimeDisplay {
    /**
     * Show a *single* approximate countdown, rounded to five-second intervals.
     * A missing/expired estimate stays unknown; an active job never shows 00:00.
     * Actual elapsed time and native completed chunk counts stay exact.
     */
    fun approximateRemainingMs(value: Long?): Long? {
        val positive = value?.takeIf { it > 0L } ?: return null
        val ticks = (positive / 5_000L + if (positive % 5_000L >= 2_500L) 1 else 0)
            .coerceAtLeast(1L)
        return ticks * 5_000L
    }
}
