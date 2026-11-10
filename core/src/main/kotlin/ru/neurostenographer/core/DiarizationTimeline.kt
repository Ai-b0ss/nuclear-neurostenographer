package ru.neurostenographer.core

import kotlin.math.roundToLong

/** Raw global cluster labels, never personal identities or confidence scores. */
data class ClusterTurn(val startSeconds: Float, val endSeconds: Float, val cluster: Int)
data class AudioWindow(val startMs: Long, val endMs: Long)

object DiarizationTimeline {
    /** Pauses shorter than this stay inside one ASR window. */
    const val MERGE_GAP_MS = 500L

    /** ASR input when segmentation has actually run: continuous detected speech
     * (including short/unknown clusters), one window per stretch without a real
     * pause, never cut at a speaker change. Turn boundaries inside a stretch are
     * left to word timestamps; stretches over 20 s are split for QuietCuts.refine.
     * Missed speech remains a model false negative; it must not be filled with guessed text.
     */
    fun speechWindows(raw: List<ClusterTurn>, audioMs: Long): List<AudioWindow> =
        speechWindowsOf(canonicalize(raw, audioMs)) // also validates native intervals

    /** The same policy over canonical turns; the parent re-derives it to validate the worker reply. */
    fun speechWindowsOf(turns: List<SpeakerTurn>): List<AudioWindow> {
        val spans = mutableListOf<LongArray>()
        turns.sortedBy { it.startMs }.forEach { turn ->
            val last = spans.lastOrNull()
            if (last != null && turn.startMs - last[1] < MERGE_GAP_MS) last[1] = maxOf(last[1], turn.endMs)
            else spans += longArrayOf(turn.startMs, turn.endMs)
        }
        return spans.flatMap { (start, end) ->
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

    /** Union of independent speech evidence: Silero and Nemotron. Neither detector
     * may erase speech found by the other. Speaker labels are never inferred here.
     * Adjacent original 20 s chunks are re-joined before applying the same cap.
     */
    fun combineSpeechWindows(c2: List<AudioWindow>, vad: List<AudioWindow>, audioMs: Long): List<AudioWindow> {
        require(audioMs >= 100)
        val all = (c2 + vad).sortedWith(compareBy<AudioWindow> { it.startMs }.thenBy { it.endMs })
        require(all.all { it.startMs >= 0 && it.endMs > it.startMs && it.endMs <= audioMs })
        val merged = mutableListOf<AudioWindow>()
        for (w in all) {
            val last = merged.lastOrNull()
            if (last != null && w.startMs - last.endMs < MERGE_GAP_MS) {
                merged[merged.lastIndex] = AudioWindow(last.startMs, maxOf(last.endMs, w.endMs))
            } else merged += w
        }
        return merged.flatMap { w ->
            val parts = mutableListOf<AudioWindow>()
            if (w.endMs - w.startMs < 100L) {
                // ASR requires at least 100 ms; preserve a tiny detected utterance.
                val begin = minOf(w.startMs, audioMs - 100L).coerceAtLeast(0L)
                parts += AudioWindow(begin, begin + 100L)
            } else {
                var at = w.startMs
                while (w.endMs - at > 20_000L) {
                    // Avoid a 1..99 ms tail that would abort transcription.
                    val tail = w.endMs - (at + 20_000L)
                    val next = if (tail in 1L..99L) w.endMs - 100L else at + 20_000L
                    parts += AudioWindow(at, next)
                    at = next
                }
                parts += AudioWindow(at, w.endMs)
            }
            parts
        }
    }

    /** Pre-0.3.2 policy, still used for ASR without word timestamps (CTC build): speech cut at every
     * turn boundary, so each fragment can be attributed as a whole. */
    fun turnWindows(turns: List<SpeakerTurn>, audioMs: Long): List<AudioWindow> =
        windows(turns, audioMs).filter { w -> turns.any { it.startMs <= w.startMs && it.endMs >= w.endMs } }

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
        require(boundaries.size <= DiarizationReply.MAX_ITEMS) { "Too many diarization boundaries" }
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
