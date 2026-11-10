package ru.neurostenographer.core

import kotlin.math.roundToLong

/**
 * Reconciles two independently produced diarization timelines without access
 * to reference labels, ASR text or future PCM.
 *
 * The final timeline MUST already be aligned to the preview's slot IDs by
 * SpeakerIdentity.align. Preview wins where it has an active speaker; offline
 * finalization fills only intervals with no preview hypothesis.
 *
 * This avoids replacing stable early identities with contradictory offline
 * output, but it cannot correct a preview that is itself confidently wrong.
 * At most two 8-slot event counters are live, independent of recording length.
 */
object SpeakerConsensus {
    data class Result(val turns: List<ClusterTurn>, val disagreementMs: Long,
                      val offlineFillMs: Long)

    private data class Event(val ms: Long, val cluster: Int,
                             val preview: Boolean, val change: Int)

    fun previewFirst(preview: List<ClusterTurn>, alignedOffline: List<ClusterTurn>): Result =
        reconcile(preview, alignedOffline, preferOffline = false)

    /** After Stop, the full-context diarization supersedes provisional live
     * hypotheses where available; the provisional timeline fills final gaps.
     * This does not claim the offline model is infallible: labels must first
     * be aligned by SpeakerIdentity.align.
     */
    fun offlineFirst(preview: List<ClusterTurn>, alignedOffline: List<ClusterTurn>): Result =
        reconcile(preview, alignedOffline, preferOffline = true)

    private fun reconcile(preview: List<ClusterTurn>, alignedOffline: List<ClusterTurn>,
                          preferOffline: Boolean): Result {
        val events = ArrayList<Event>((preview.size + alignedOffline.size) * 2)

        fun add(turns: List<ClusterTurn>, isPreview: Boolean) {
            for (t in turns) {
                require(t.cluster in 0..7 &&
                    t.startSeconds.isFinite() && t.endSeconds.isFinite() &&
                    t.startSeconds >= 0f && t.endSeconds > t.startSeconds &&
                    t.endSeconds <= 3600.1f) { "Invalid speaker interval" }
                val from = (t.startSeconds.toDouble() * 1000.0).roundToLong()
                val until = (t.endSeconds.toDouble() * 1000.0).roundToLong()
                if (until > from) {
                    events += Event(from, t.cluster, isPreview, 1)
                    events += Event(until, t.cluster, isPreview, -1)
                }
            }
        }
        add(preview, true)
        add(alignedOffline, false)
        if (events.isEmpty()) return Result(emptyList(), 0L, 0L)
        events.sortBy { it.ms }

        val previewCounts = IntArray(8)
        val finalCounts = IntArray(8)
        val openedAt = LongArray(8) { -1L }
        val result = ArrayList<ClusterTurn>()
        var disagreement = 0L
        var offlineFill = 0L
        var cursor = events[0].ms
        var index = 0
        while (index < events.size) {
            val at = events[index].ms
            if (at > cursor) {
                val activePreview = previewCounts.any { it > 0 }
                val activeOffline = finalCounts.any { it > 0 }
                if (activePreview != activeOffline ||
                    (0..7).any { (previewCounts[it] > 0) != (finalCounts[it] > 0) }) {
                    disagreement += at - cursor
                }
                if (!activePreview && activeOffline) offlineFill += at - cursor
            }
            while (index < events.size && events[index].ms == at) {
                val event = events[index++]
                val counts = if (event.preview) previewCounts else finalCounts
                counts[event.cluster] += event.change
                check(counts[event.cluster] >= 0) { "Unbalanced speaker intervals" }
            }
            val hasPreview = previewCounts.any { it > 0 }
            for (slot in 0..7) {
                val active = if (preferOffline) {
                    if (finalCounts.any { it > 0 }) finalCounts[slot] > 0 else previewCounts[slot] > 0
                } else {
                    if (hasPreview) previewCounts[slot] > 0 else finalCounts[slot] > 0
                }
                if (active && openedAt[slot] < 0) openedAt[slot] = at
                if (!active && openedAt[slot] >= 0) {
                    if (at > openedAt[slot]) {
                        result += ClusterTurn(openedAt[slot] / 1000f, at / 1000f, slot)
                    }
                    openedAt[slot] = -1
                }
            }
            cursor = at
        }
        check(openedAt.all { it == -1L } &&
            previewCounts.all { it == 0 } && finalCounts.all { it == 0 })
        return Result(result.sortedWith(compareBy<ClusterTurn> { it.startSeconds }
            .thenBy { it.cluster }), disagreement, offlineFill)
    }
}
