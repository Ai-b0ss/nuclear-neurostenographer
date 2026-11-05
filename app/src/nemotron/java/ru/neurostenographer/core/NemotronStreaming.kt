// SPDX-License-Identifier: LicenseRef-OpenMDW-1.1
package ru.neurostenographer.core

/** Counts in 80-ms encoder frames. Both streaming modes share cache/FIFO state. */
data class NemotronChunkConfig(val chunk: Int, val right: Int, val fifo: Int, val update: Int) {
    init { require(chunk in 1..340 && right in 0..40 && fifo in 1..512 && update in 1..512) }
    companion object {
        val OFFLINE = NemotronChunkConfig(340, 40, 40, 300)
        val FAST = NemotronChunkConfig(45, 6, 264, 222)
        val FALLBACK = NemotronChunkConfig(120, 13, 264, 222)
    }
}

/** Persistent session cache; each captured frame is committed exactly once.
 * Mel uses only already captured PCM and waits for centered STFT's 256-sample lookahead.
 * Zero padding and the export's zero trailing mel frame are allowed only at EOF. */
class NemotronStreaming(private val filters: FloatArray, private val hann: FloatArray,
    silence: FloatArray, private val runner: NemotronChunkRunner,
    initial: NemotronChunkConfig = NemotronChunkConfig.FAST) {
    private val cache = NemotronSpeakerCache(silence, initial.fifo, initial.update)
    var config = initial
        set(value) {
            require(value.fifo == field.fifo && value.update == field.update) { "Cannot reset session cache during adaptation" }
            field = value
        }
    private var start = 0
    private var written = 0
    private val opened = IntArray(8) { -1 }
    private val turns = mutableListOf<ClusterTurn>()
    var calls = 0
        private set
    val committedSamples get() = written * 160L
    val contextFrames get() = cache.contextFrames()

    fun canStep(available: Long, eof: Boolean): Boolean {
        if (eof) return start < ((1 + available / 160 + 7) / 8)
        // Last mel frame needs samples through center+255, and preemphasis needs center-257.
        return available >= (start + config.chunk + config.right) * 1280L + 256
    }

    fun step(available: Long, eof: Boolean, read: (Long, Int) -> FloatArray): List<ClusterTurn> {
        require(available in 1..3600L * 16000 && canStep(available, eof))
        val melFrames = 1 + available.toInt() / 160
        val embeddings = (melFrames + 7) / 8
        val end = minOf(start + config.chunk, embeddings)
        val count = end - start
        val melStart = start * 8
        val melEnd = minOf((end + config.right) * 8, melFrames)
        val first = maxOf(0L, melStart * 160L - 257)
        val last = minOf(available, (melEnd - 1) * 160L + 256)
        val pcm = read(first, (last - first).toInt())
        require(pcm.size == (last - first).toInt())
        val mel = NemotronMel(FloatArray(0), filters, hann, available.toInt(), eof) { pcm[it - first.toInt()] }
        val chunk = FloatArray((melEnd - melStart) * 128)
        mel.write(melStart, melEnd - melStart, chunk)
        val context = cache.contextFrames()
        val result = runner.run(chunk, melEnd - melStart, maxOf(0, minOf(melEnd, melFrames - 1) - melStart),
            cache.context(), context)
        require(result.logits.size == result.logitFrames * 8 && result.embeds.size == result.embedFrames * 512 &&
            result.logitFrames >= (context + count) * 8 && result.embedFrames >= context + count &&
            result.logits.all { it.isFinite() } && result.embeds.all { it.isFinite() }) { "Malformed C2 step" }
        cache.update(result, count)
        val until = minOf((context + count) * 8, context * 8 + melFrames - written)
        for (row in context * 8 until until) {
            for (s in 0..7) {
                val active = result.logits[row * 8 + s] > 0f
                if (active && opened[s] < 0) opened[s] = written
                if (!active && opened[s] >= 0) {
                    if (written > opened[s]) turns += ClusterTurn(opened[s] * 0.01f, written * 0.01f, s)
                    opened[s] = -1
                }
            }
            written++
        }
        start = end; calls++
        return snapshot(available)
    }

    fun snapshot(available: Long): List<ClusterTurn> {
        val duration = available / 16000f
        return (turns + opened.indices.mapNotNull { s ->
            if (opened[s] >= 0 && written > opened[s]) ClusterTurn(opened[s] * 0.01f, written * 0.01f, s) else null
        }).mapNotNull { t ->
            val end = minOf(t.endSeconds, duration)
            if (end > t.startSeconds) t.copy(endSeconds = end) else null
        }.sortedWith(compareBy<ClusterTurn> { it.startSeconds }.thenBy { it.cluster })
    }
}
