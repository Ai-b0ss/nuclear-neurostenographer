package ru.neurostenographer.core

import kotlin.math.sqrt

/** Default consistent-enrollment fusion. A lower construction cutoff alone never authorizes identity. */
object VoicePrintAgreement {
    fun mergeIfConsistent(first: FloatArray, second: FloatArray,
                          minCosine: Double = 0.84): FloatArray? {
        if (first.size !in 2..4096 || second.size != first.size ||
            minCosine !in 0.0..1.0 || first.any { !it.isFinite() } ||
            second.any { !it.isFinite() }) return null

        fun norm(values: FloatArray): Double {
            var sum = 0.0
            for (v in values) sum += v.toDouble() * v
            return sqrt(sum)
        }
        val len1 = norm(first)
        val len2 = norm(second)
        if (!len1.isFinite() || !len2.isFinite() ||
            len1 < 1e-8 || len2 < 1e-8) return null
        var dot = 0.0
        for (i in first.indices) dot += first[i].toDouble() * second[i]
        if (dot / (len1 * len2) < minCosine) return null

        val mixed = FloatArray(first.size) {
            (first[it] / len1 + second[it] / len2).toFloat()
        }
        val len = norm(mixed)
        return if (!len.isFinite() || len < 1e-8) null
            else FloatArray(mixed.size) { (mixed[it] / len).toFloat() }
    }
}
