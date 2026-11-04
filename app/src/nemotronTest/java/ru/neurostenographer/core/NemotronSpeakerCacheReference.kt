package ru.neurostenographer.core

import kotlin.math.*

/** Kotlin reference cache retained for numerical checks of the C++ port. */
class NemotronSpeakerCacheReference(private val silence: FloatArray) {
    private val hidden = NemotronConfig.HIDDEN
    private val speakers = NemotronConfig.SPEAKERS
    private val length = NemotronConfig.CACHE
    private val budget = length / speakers - NemotronConfig.SILENCE_FRAMES
    private val minPositive = floor(budget * NemotronConfig.MIN_POSITIVE_RATE).toInt()
    private val strong = floor(budget * NemotronConfig.STRONG_RATE).toInt()
    private val weak = floor(budget * NemotronConfig.WEAK_RATE).toInt()
    private var embeds = FloatArray(length * hidden)
    private var probs = FloatArray(length * speakers)
    private val fifo = FloatArray(NemotronConfig.FIFO * hidden)
    var cacheFrames = 0
        private set
    var fifoFrames = 0
        private set
    private var compressed = false

    init { require(silence.size == hidden) }

    fun contextFrames() = cacheFrames + fifoFrames

    fun context(): FloatArray {
        val out = FloatArray(contextFrames() * hidden)
        embeds.copyInto(out, 0, 0, cacheFrames * hidden)
        fifo.copyInto(out, cacheFrames * hidden, 0, fifoFrames * hidden)
        return out
    }

    private fun sigmoid(x: Float): Float {
        val z = exp(-abs(x))
        return if (x >= 0) 1f / (1f + z) else z / (1f + z)
    }

    private fun pool(logits: FloatArray, logitFrames: Int): FloatArray {
        val factor = NemotronConfig.SUBSAMPLING
        val frames = logitFrames / factor
        val out = FloatArray(frames * speakers)
        for (f in 0 until frames) for (s in 0 until speakers) {
            var sum = 0f
            for (k in 0 until factor) sum += sigmoid(logits[(f * factor + k) * speakers + s])
            out[f * speakers + s] = sum / factor
        }
        return out
    }

    fun update(step: NemotronStep, chunkFrames: Int) {
        val pooled = pool(step.logits, step.logitFrames)
        val chunkStart = cacheFrames + fifoFrames
        val pending = fifoFrames + chunkFrames
        var fifoEmbeds = FloatArray(pending * hidden)
        fifo.copyInto(fifoEmbeds, 0, 0, fifoFrames * hidden)
        step.embeds.copyInto(fifoEmbeds, fifoFrames * hidden, chunkStart * hidden, (chunkStart + chunkFrames) * hidden)
        var remaining = pending
        val popped = if (pending <= NemotronConfig.FIFO) 0 else min(max(NemotronConfig.UPDATE_PERIOD, pending - NemotronConfig.FIFO), pending)
        if (popped > 0) {
            var rows = cacheFrames + popped
            var cacheEmbeds = FloatArray(rows * hidden)
            var cacheProbs = FloatArray(rows * speakers)
            embeds.copyInto(cacheEmbeds, 0, 0, cacheFrames * hidden)
            fifoEmbeds.copyInto(cacheEmbeds, cacheFrames * hidden, 0, popped * hidden)
            (if (compressed) probs else pooled).copyInto(cacheProbs, 0, 0, cacheFrames * speakers)
            pooled.copyInto(cacheProbs, cacheFrames * speakers, cacheFrames * speakers, (cacheFrames + popped) * speakers)
            remaining = pending - popped
            fifoEmbeds = fifoEmbeds.copyOfRange(popped * hidden, pending * hidden)
            if (rows > length) {
                val kept = compress(cacheEmbeds, cacheProbs, rows)
                cacheEmbeds = kept.first
                cacheProbs = kept.second
                compressed = true
                rows = length
            }
            cacheFrames = rows
            cacheEmbeds.copyInto(embeds, 0, 0, rows * hidden)
            cacheProbs.copyInto(probs, 0, 0, rows * speakers)
        }
        fifoFrames = remaining
        fifoEmbeds.copyInto(fifo, 0, 0, remaining * hidden)
    }

    private fun scores(probabilities: FloatArray, frames: Int): FloatArray {
        val threshold = NemotronConfig.SCORE_THRESHOLD
        val log05 = ln(0.5).toFloat()
        val out = FloatArray(frames * speakers)
        val positive = IntArray(speakers)
        for (f in 0 until frames) {
            var complements = 0f
            for (s in 0 until speakers) complements += ln(max(1f - probabilities[f * speakers + s], threshold))
            for (s in 0 until speakers) {
                val p = probabilities[f * speakers + s]
                val value = if (p > 0.5f) ln(max(p, threshold)) - ln(max(1f - p, threshold)) + complements - log05 else Float.NEGATIVE_INFINITY
                out[f * speakers + s] = value
                if (value > 0) positive[s]++
            }
        }
        for (f in 0 until frames) for (s in 0 until speakers) {
            val at = f * speakers + s
            if (out[at] <= 0 && probabilities[at] > 0.5f && positive[s] >= minPositive) out[at] = Float.NEGATIVE_INFINITY
        }
        return out
    }

    /** Largest values first; ties keep the lower index, like stable_topk_indices. */
    private fun topK(count: Int, take: Int, value: (Int) -> Float): List<Int> =
        (0 until count).sortedWith(compareBy<Int> { -value(it) }.thenBy { it }).take(take)

    private fun boost(scores: FloatArray, frames: Int, count: Int, amount: Float) {
        if (count <= 0) return
        for (s in 0 until speakers) {
            for (f in topK(frames, count) { scores[it * speakers + s] }) scores[f * speakers + s] += amount
        }
    }

    private fun compress(cacheEmbeds: FloatArray, cacheProbs: FloatArray, frames: Int): Pair<FloatArray, FloatArray> {
        val scored = scores(cacheProbs, frames)
        for (f in length until frames) for (s in 0 until speakers) scored[f * speakers + s] += NemotronConfig.LATEST_BOOST
        boost(scored, frames, strong, (-2.0 * ln(0.5)).toFloat())
        boost(scored, frames, weak, (-ln(0.5)).toFloat())
        val rows = frames + NemotronConfig.SILENCE_FRAMES
        val sentinel = rows * speakers
        val flat = { index: Int ->
            val frame = index % rows
            if (frame >= frames) Float.POSITIVE_INFINITY else scored[frame * speakers + index / rows]
        }
        val chosen = topK(sentinel, length, flat).map { if (flat(it) == Float.NEGATIVE_INFINITY) sentinel else it }.sorted()
        val outEmbeds = FloatArray(length * hidden)
        val outProbs = FloatArray(length * speakers)
        for ((row, index) in chosen.withIndex()) {
            val frame = if (index == sentinel) frames else min(index % rows, frames)
            if (frame >= frames) {
                silence.copyInto(outEmbeds, row * hidden)
            } else {
                cacheEmbeds.copyInto(outEmbeds, row * hidden, frame * hidden, (frame + 1) * hidden)
                cacheProbs.copyInto(outProbs, row * speakers, frame * speakers, (frame + 1) * speakers)
            }
        }
        return outEmbeds to outProbs
    }
}

