// SPDX-License-Identifier: LicenseRef-OpenMDW-1.1
package ru.neurostenographer.core

/** The production chunk loop, including model calls and speaker cache, runs in C++. */
internal object NativeNemotronPipeline {
    init { System.loadLibrary("nemotron_native") }

    private external fun run(wave: FloatArray, filters: FloatArray, hann: FloatArray,
                             silence: FloatArray, modelPath: String, threads: Int,
                             checkCancelled: () -> Unit, activityThreshold: Float,
                             exclusiveGapThreshold: Float,
                             timing: LongArray): FloatArray

    fun diarize(wave: FloatArray, filters: FloatArray, hann: FloatArray, silence: FloatArray,
                modelPath: String, threads: Int, checkCancelled: () -> Unit,
                activityThreshold: Float = 0f,
                exclusiveGapThreshold: Float = 0f): Triple<List<ClusterTurn>, Long, Long> {
        val timing = LongArray(2)
        val packed = run(wave, filters, hann, silence, modelPath, threads, checkCancelled,
            activityThreshold, exclusiveGapThreshold, timing)
        require(packed.size % 3 == 0) { "Invalid native Nemotron turns" }
        return Triple(packed.asList().chunked(3).map { ClusterTurn(it[0], it[1], it[2].toInt()) },
            timing[0], timing[1])
    }
}
