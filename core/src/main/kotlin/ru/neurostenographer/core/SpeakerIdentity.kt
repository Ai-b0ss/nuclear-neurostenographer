package ru.neurostenographer.core

/** Align a fresh finalization session to provisional display IDs by maximum temporal
 * agreement. One-to-one assignment prevents merging distinct voices. No reference labels,
 * assumed speaker count, or claim that encoder states are speaker embeddings. */
object SpeakerIdentity {
    fun align(final: List<ClusterTurn>, provisional: List<ClusterTurn>): List<ClusterTurn> {
        val weights = Array(8) { DoubleArray(8) }
        require((final + provisional).all { it.cluster in 0..7 })
        val finals = final.groupBy { it.cluster }
        val previews = provisional.groupBy { it.cluster }
        for ((aId, aTurns) in finals) for ((bId, bTurns) in previews) {
            val aa = aTurns.sortedBy { it.startSeconds }; val bb = bTurns.sortedBy { it.startSeconds }
            var i = 0; var j = 0
            while (i < aa.size && j < bb.size) {
                val a = aa[i]; val b = bb[j]
                weights[aId][bId] += maxOf(0f, minOf(a.endSeconds, b.endSeconds) - maxOf(a.startSeconds, b.startSeconds)).toDouble()
                if (a.endSeconds < b.endSeconds) i++ else j++
            }
        }
        val score = DoubleArray(256) { Double.NEGATIVE_INFINITY }
        val parent = IntArray(256) { -1 }
        score[0] = 0.0
        for (mask in 0 until 255) {
            val row = Integer.bitCount(mask)
            for (slot in 0..7) if (mask and (1 shl slot) == 0) {
                val next = mask or (1 shl slot)
                // Tiny deterministic preference preserves absent/unchanged slots on ties.
                val candidate = score[mask] + weights[row][slot] + if (row == slot) 1e-9 else 0.0
                if (candidate > score[next]) { score[next] = candidate; parent[next] = slot }
            }
        }
        val mapping = IntArray(8)
        var mask = 255
        for (row in 7 downTo 0) { mapping[row] = parent[mask]; mask = mask xor (1 shl mapping[row]) }
        return final.map { it.copy(cluster = mapping[it.cluster]) }
    }
}
