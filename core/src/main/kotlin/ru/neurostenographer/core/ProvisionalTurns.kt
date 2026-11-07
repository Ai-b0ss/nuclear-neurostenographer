package ru.neurostenographer.core

/**
 * Duration smoothing for provisional (live) C2 turns, the duration half of NemotronPostprocess.PRODUCT:
 * per speaker, gaps up to [minOffMs] are closed, then turns shorter than [minOnMs] are dropped.
 * Live C2 keeps only frame masks, not logits, so the threshold half cannot apply here; the
 * full-recording pass after Stop uses the complete post-processing.
 */
object ProvisionalTurns {
    fun smooth(turns: List<ClusterTurn>, minOnMs: Int = 240, minOffMs: Int = 400): List<ClusterTurn> {
        require(minOnMs >= 0 && minOffMs >= 0)
        val out = mutableListOf<ClusterTurn>()
        for ((cluster, own) in turns.groupBy { it.cluster }) {
            val merged = mutableListOf<LongArray>()
            for (t in own.sortedBy { it.startSeconds }) {
                val a = Math.round(t.startSeconds * 1000.0); val b = Math.round(t.endSeconds * 1000.0)
                val last = merged.lastOrNull()
                if (last != null && a - last[1] <= minOffMs) last[1] = maxOf(last[1], b) else merged += longArrayOf(a, b)
            }
            for ((a, b) in merged.map { it[0] to it[1] }) if (b - a >= minOnMs) out += ClusterTurn(a / 1000f, b / 1000f, cluster)
        }
        return out.sortedWith(compareBy<ClusterTurn> { it.startSeconds }.thenBy { it.cluster })
    }
}
