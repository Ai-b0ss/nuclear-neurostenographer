package ru.neurostenographer.core

import kotlin.math.roundToLong

/** Raw global cluster labels, never personal identities or confidence scores. */
data class ClusterTurn(val startSeconds: Float, val endSeconds: Float, val cluster: Int)
data class AudioWindow(val startMs: Long, val endMs: Long)

object DiarizationTimeline {
    /** Use detected speech (including short/unknown clusters), not silence gaps,
     * as ASR input when segmentation has actually run. Missed speech remains a
     * model false negative; it must not be filled with guessed text.
     */
    fun speechWindows(raw: List<ClusterTurn>, audioMs: Long): List<AudioWindow> {
        canonicalize(raw, audioMs) // validate native intervals
        val speech = raw.mapNotNull {
            val start = (it.startSeconds * 1000.0).roundToLong().coerceAtMost(audioMs)
            val end = (it.endSeconds * 1000.0).roundToLong().coerceAtMost(audioMs)
            if (end > start) SpeakerTurn(start, end, "speech") else null
        }
        return windows(speech, audioMs).filter { window ->
            speech.any { it.startMs <= window.startMs && it.endMs >= window.endMs }
        }
    }

    /** Deterministic first-appearance names, scoped to one complete recording. */
    fun canonicalize(raw: List<ClusterTurn>, audioMs: Long): List<SpeakerTurn> {
        require(audioMs > 0)
        require(raw.all { it.startSeconds.isFinite() && it.endSeconds.isFinite() &&
            it.startSeconds >= 0 && it.endSeconds > it.startSeconds }) { "Invalid native diarization interval" }
        val clipped = raw.mapNotNull {
            val start = (it.startSeconds * 1000.0).roundToLong().coerceAtMost(audioMs)
            val end = (it.endSeconds * 1000.0).roundToLong().coerceAtMost(audioMs)
            // Preserve even uncertain evidence so a brief interruption cannot
            // disappear and incorrectly make a longer voice look unambiguous.
            if (end > start) Triple(start, end, it.cluster) else null
        }.sortedWith(compareBy<Triple<Long, Long, Int>> { it.first }.thenBy { it.third }.thenBy { it.second })
        val names = linkedMapOf<Int, String>()
        return clipped.map { (start, end, cluster) ->
            SpeakerTurn(start, end, if (cluster < 0) "Unknown" else
                names.getOrPut(cluster) { "Speaker ${names.size + 1}" },
                attributionEligible = cluster >= 0 && end - start >= 300)
        }.distinct()
    }

    /** Partition at actual inferred turn boundaries; no invented word alignment.
     * Uncovered audio is decoded too, with unknown attribution. Tiny gaps <100 ms
     * are skipped rather than expanding them into fake one-second utterances.
     */
    fun windows(turns: List<SpeakerTurn>, audioMs: Long): List<AudioWindow> {
        require(audioMs > 0 && audioMs <= PcmWav.MAX_SECONDS * 1000L)
        require(turns.all { it.endMs <= audioMs })
        val boundaries = (listOf(0L, audioMs) + turns.flatMap { listOf(it.startMs, it.endMs) }).distinct().sorted()
        require(boundaries.size <= 2000) { "Too many diarization boundaries" }
        return boundaries.zipWithNext().flatMap { (start, end) ->
            val out = mutableListOf<AudioWindow>()
            var at = start
            while (at < end) {
                val next = minOf(at + 20_000, end)
                if (next - at >= 100) out += AudioWindow(at, next)
                at = next
            }
            out
        }
    }
}
