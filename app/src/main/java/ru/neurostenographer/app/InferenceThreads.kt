package ru.neurostenographer.app

/** Threads for ONNX Runtime. Measured on a Kirin 710 phone (4 fast + 4 slow cores): 2 threads 95.9 s,
 * 4 threads 63.5 s, 8 threads 101.4 s of diarization for a 42 s recording, so 4 is the cap. Small devices keep what they have.
 */
object InferenceThreads {
    const val MAX = 4
    // RNNT uses several sessions. Four threads per session exceeded the HONOR
    // sustained CPU cutoff during ASR; batch recognition uses the balanced cap.
    const val BATCH_ASR_MAX = 2
    fun batchAsrCount(processors: Int = Runtime.getRuntime().availableProcessors()) =
        processors.coerceIn(1, BATCH_ASR_MAX)

    fun count(processors: Int = Runtime.getRuntime().availableProcessors()) = processors.coerceIn(1, MAX)
}
