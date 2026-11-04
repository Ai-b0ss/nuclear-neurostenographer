package ru.neurostenographer.core

/** Wall-clock limit for decoding a compressed file to PCM. A fixed 60 s rejects long
 * recordings on slow phones; the limit grows with the declared duration but stays bounded.
 */
object DecodeBudget {
    const val MIN_MS = 60_000L
    const val MAX_MS = 10 * 60_000L
    const val UNKNOWN_DURATION_MS = 5 * 60_000L

    fun millis(declaredDurationMs: Long?): Long {
        if (declaredDurationMs == null || declaredDurationMs <= 0) return UNKNOWN_DURATION_MS
        return (declaredDurationMs / 2).coerceIn(MIN_MS, MAX_MS)
    }
}
