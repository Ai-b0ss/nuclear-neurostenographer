package ru.neurostenographer.core

import kotlin.math.sqrt

/** Long recordings: only embeddings from clean speech can link C2's local speaker labels.
 * Similarity is NOT probability. Use experimentally until independent validation.
 */
data class VoicePrint(val localSpeakerId: String, val embedding: FloatArray, val cleanSpeechMs: Long)

class GlobalSpeakerBook(
    private val minCleanMs: Long = 2400,
    private val minCosine: Double = 0.84,
    private val minMargin: Double = 0.07
) {
    private data class Entry(val id: String, var centroid: DoubleArray)
    private data class Candidate(val id: String, val vector: DoubleArray,
                                 val topIndex: Int, val top: Double, val runnerUp: Double)
    private val entries = mutableListOf<Entry>()
    private var nextId = 1

    init { require(minCleanMs >= 1500 && minCosine in 0.0..1.0 && minMargin in 0.0..1.0) }

    /** Compare only with earlier blocks. Colliding or ambiguous matches MUST NOT merge people. */
    fun link(profiles: List<VoicePrint>): Map<String, String> {
        require(profiles.size <= 8 && profiles.map { it.localSpeakerId }.distinct().size == profiles.size)
        val candidates = profiles.mapNotNull { p ->
            if (p.localSpeakerId.isBlank() || p.cleanSpeechMs < minCleanMs) return@mapNotNull null
            val v = normalized(p.embedding) ?: return@mapNotNull null
            if (entries.isNotEmpty() && v.size != entries[0].centroid.size) return@mapNotNull null
            val ranked = entries.mapIndexed { index, e -> index to dot(v, e.centroid) }
                .sortedByDescending { it.second }
            Candidate(p.localSpeakerId, v, ranked.firstOrNull()?.first ?: -1,
                ranked.firstOrNull()?.second ?: -1.0, ranked.getOrNull(1)?.second ?: -1.0)
        }
        val eligible = candidates.filter { it.topIndex >= 0 && it.top >= minCosine &&
            it.top - it.runnerUp >= minMargin }
        val collisions = eligible.groupingBy { it.topIndex }.eachCount()
        val result = linkedMapOf<String, String>()
        val updates = mutableListOf<Pair<Int, DoubleArray>>()
        val fresh = mutableListOf<Candidate>()
        for (c in candidates) {
            if (c in eligible && collisions[c.topIndex] == 1) {
                result[c.id] = entries[c.topIndex].id
                updates += c.topIndex to c.vector
            } else fresh += c
        }
        for ((idx, vector) in updates) {
            val old = entries[idx]
            val blended = DoubleArray(vector.size) { old.centroid[it] * 0.85 + vector[it] * 0.15 }
            old.centroid = normalized(blended) ?: old.centroid
        }
        for (c in fresh) {
            if (entries.size == 256) break
            val id = "Speaker " + nextId++
            entries += Entry(id, c.vector)
            result[c.id] = id
        }
        return result
    }

    fun size() = entries.size

    private fun normalized(values: FloatArray): DoubleArray? {
        if (values.size !in 2..4096 || values.any { !it.isFinite() }) return null
        return normalized(DoubleArray(values.size) { values[it].toDouble() })
    }
    private fun normalized(v: DoubleArray): DoubleArray? {
        val norm = sqrt(v.sumOf { it * it })
        return if (!norm.isFinite() || norm < 1e-9) null else DoubleArray(v.size) { v[it] / norm }
    }
    private fun dot(a: DoubleArray, b: DoubleArray): Double {
        var sum = 0.0
        for (i in a.indices) sum += a[i] * b[i]
        return sum
    }
}
