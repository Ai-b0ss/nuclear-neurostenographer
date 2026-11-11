package ru.neurostenographer.core

import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.roundToLong
import kotlin.math.sqrt

/**
 * Collect cautious voice evidence from the 512-dimensional C2 encoder output.
 * It is NOT a speaker-verification model: its cross-window separability requires
 * independent evaluation. Never use these vectors to infer a person's real identity.
 */
object NemotronVoiceProfiles {
    const val STRIDE_MS = 80
    const val DIM = NemotronConfig.HIDDEN

    /** Embeddings at 80-ms intervals; only fully covered, single-speaker frames count. */
    fun aggregate(turns: List<ClusterTurn>, embeddings: FloatArray,
                  frames: Int, audioMs: Long, dimension: Int = DIM): List<VoicePrint> {
        require(frames >= 0 && frames <= 20_000 && dimension in 2..4096 &&
            embeddings.size == frames * dimension && audioMs > 0)
        if (frames == 0 || turns.isEmpty()) return emptyList()

        val active = IntArray(frames) { -1 }
        val complete = IntArray(frames) { -1 }
        val observed = linkedMapOf<Int, Long>()
        val sorted = turns.sortedWith(compareBy<ClusterTurn> {
            (it.startSeconds * 1000.0).roundToLong()
        }.thenBy { it.cluster }.thenBy { (it.endSeconds * 1000.0).roundToLong() })
        for (t in sorted) {
            if (!t.startSeconds.isFinite() || !t.endSeconds.isFinite() ||
                t.startSeconds < 0 || t.endSeconds <= t.startSeconds ||
                t.cluster !in 0 until NemotronConfig.SPEAKERS) return emptyList()
            val start = (t.startSeconds * 1000.0).roundToLong().coerceAtMost(audioMs)
            val end = (t.endSeconds * 1000.0).roundToLong().coerceAtMost(audioMs)
            if (end <= start) continue
            if (t.cluster !in observed) observed[t.cluster] = start
            val lo = (start / STRIDE_MS).toInt().coerceIn(0, frames)
            val hi = ((end + STRIDE_MS - 1) / STRIDE_MS).toInt().coerceIn(0, frames)
            for (f in lo until hi) {
                if (active[f] == -1) active[f] = t.cluster
                else if (active[f] != t.cluster) active[f] = -2
            }
            val fullLo = ((start + STRIDE_MS - 1) / STRIDE_MS).toInt().coerceIn(0, frames)
            val fullHi = (end / STRIDE_MS).toInt().coerceIn(0, frames)
            for (f in fullLo until fullHi) complete[f] = t.cluster
        }

        val sums = Array(NemotronConfig.SPEAKERS) { DoubleArray(dimension) }
        val counts = IntArray(NemotronConfig.SPEAKERS)
        for (f in 0 until frames) {
            val s = active[f]
            if (s < 0 || complete[f] != s || s !in observed) continue
            val from = f * dimension
            var norm2 = 0.0
            for (j in 0 until dimension) {
                val x = embeddings[from + j]
                if (!x.isFinite()) { norm2 = 0.0; break }
                norm2 += x.toDouble() * x
            }
            if (norm2 < 1e-9) continue
            val inv = 1.0 / sqrt(norm2)
            for (j in 0 until dimension) sums[s][j] += embeddings[from + j] * inv
            counts[s]++
        }
        val order = observed.keys.toList()
        return order.mapIndexedNotNull { i, slot ->
            if (counts[slot] * STRIDE_MS < 1500) return@mapIndexedNotNull null
            val values = FloatArray(dimension) { sums[slot][it].toFloat() }
            VoicePrint("Speaker " + (i + 1), values, counts[slot].toLong() * STRIDE_MS)
        }
    }
}
