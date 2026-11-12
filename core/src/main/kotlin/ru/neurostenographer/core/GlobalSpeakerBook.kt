package ru.neurostenographer.core

import kotlin.math.sqrt

/** Similarity is not probability. Global identity remains experimental. */
data class VoicePrint(val localSpeakerId: String, val embedding: FloatArray, val cleanSpeechMs: Long,
    val earlyEmbedding: FloatArray? = null, val lateEmbedding: FloatArray? = null,
    val earlySpeechMs: Long = 0, val lateSpeechMs: Long = 0)

class GlobalSpeakerBook(
    private val minCleanMs: Long = 2400,
    private val minCosine: Double = 0.84,
    private val minMargin: Double = 0.07
) {
    private data class Entry(val id: String, val anchor: DoubleArray, var centroid: DoubleArray)
    private data class Candidate(val id: String, val vector: DoubleArray,
                                 val target: Int?, val canEnroll: Boolean)
    private val entries = mutableListOf<Entry>()
    private var nextId = 1
    init { require(minCleanMs >= 1500 && minCosine in 0.0..1.0 && minMargin in 0.0..1.0) }

    /** Snapshot all matches before updates/enrollments. Collision blocks every claimant. */
    fun link(profiles: List<VoicePrint>): Map<String, String> {
        require(profiles.size <= 8 && profiles.map { it.localSpeakerId }.distinct().size == profiles.size)
        if (profiles.map { it.embedding.size }.distinct().size > 1) return emptyMap()
        val candidates = profiles.mapNotNull { p ->
            if (p.localSpeakerId.isBlank() || p.cleanSpeechMs < minCleanMs) return@mapNotNull null
            val supplied = normalized(p.embedding) ?: return@mapNotNull null
            if (entries.isNotEmpty() && supplied.size != entries[0].anchor.size) return@mapNotNull null
            val hasPair = p.earlyEmbedding != null || p.lateEmbedding != null ||
                p.earlySpeechMs != 0L || p.lateSpeechMs != 0L
            if (!hasPair) {
                // Compatibility for existing trusted core callers; Android IPC requires pairs.
                Candidate(p.localSpeakerId, supplied, match(supplied), true)
            } else {
                val early = p.earlyEmbedding?.let(::normalized) ?: return@mapNotNull null
                val late = p.lateEmbedding?.let(::normalized) ?: return@mapNotNull null
                if (early.size != supplied.size || late.size != supplied.size ||
                    p.earlySpeechMs !in 3000L..16000L || p.lateSpeechMs !in 3000L..16000L ||
                    p.cleanSpeechMs != p.earlySpeechMs + p.lateSpeechMs) return@mapNotNull null
                val merged = normalized(DoubleArray(early.size) { early[it] + late[it] })
                    ?: return@mapNotNull null
                if (dot(merged, supplied) < 0.99999) return@mapNotNull null
                val consistent = dot(early, late) >= minCosine
                val target = if (consistent) match(merged) else {
                    val first = match(early)
                    first?.takeIf { it == match(late) }
                }
                Candidate(p.localSpeakerId, merged, target, consistent)
            }
        }
        val collisions = candidates.mapNotNull { it.target }.groupingBy { it }.eachCount()
        val result = linkedMapOf<String, String>()
        val updates = mutableListOf<Pair<Int, DoubleArray>>()
        val fresh = mutableListOf<Candidate>()
        for (c in candidates) {
            val idx = c.target
            if (idx != null && collisions[idx] == 1) {
                result[c.id] = entries[idx].id
                // A rescued mismatch may reuse an ID but can never move its centroid/anchor.
                if (c.canEnroll) updates += idx to c.vector
            } else if (c.canEnroll) fresh += c
        }
        for ((idx, vector) in updates) {
            val old = entries[idx]
            old.centroid = normalized(DoubleArray(vector.size) {
                old.centroid[it] * 0.85 + vector[it] * 0.15
            }) ?: old.centroid
        }
        for (c in fresh) {
            if (entries.size == 256) break
            val id = "Speaker " + nextId++
            entries += Entry(id, c.vector.copyOf(), c.vector.copyOf())
            result[c.id] = id
        }
        return result
    }

    private fun match(v: DoubleArray): Int? {
        val ranked = entries.mapIndexed { i, e -> i to dot(v, e.centroid) }.sortedByDescending { it.second }
        val top = ranked.firstOrNull() ?: return null
        val runner = ranked.getOrNull(1)?.second ?: -1.0
        val anchor = dot(v, entries[top.first].anchor)
        val other = entries.indices.filter { it != top.first }.maxOfOrNull { dot(v, entries[it].anchor) } ?: -1.0
        return top.first.takeIf { top.second >= minCosine && top.second - runner >= minMargin &&
            anchor >= minCosine && anchor - other >= minMargin }
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
    private fun dot(a: DoubleArray, b: DoubleArray): Double = a.indices.sumOf { a[it] * b[it] }
}
