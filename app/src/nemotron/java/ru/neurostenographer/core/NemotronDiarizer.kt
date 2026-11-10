// SPDX-License-Identifier: LicenseRef-OpenMDW-1.1
// Kotlin port of diarize.py from joosthel/Nemotron-3-Diarization-ONNX (Copyright 2026 Joost Helfers),
// revision 4a911fc3ca821b76a99fffd5ce5135bd1efca540. See docs/NEMOTRON_ANDROID.md.
package ru.neurostenographer.core

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.floor
import kotlin.math.abs
import kotlin.math.ln
import kotlin.math.min
import kotlin.math.max
import kotlin.math.sin
import kotlin.math.sqrt

/** One chunk through the encoder graph: flattened [frames, 8] logits and [frames, 512] embeddings. */
class NemotronStep(val logits: FloatArray, val logitFrames: Int, val embeds: FloatArray, val embedFrames: Int)

fun interface NemotronChunkRunner {
    fun run(chunkMel: FloatArray, melFrames: Int, melLength: Int, context: FloatArray, contextFrames: Int): NemotronStep
}

/** Fixed export constants; the provisioning script checks them against the pinned constants.npz. */
object NemotronConfig {
    const val HIDDEN = 512
    const val SPEAKERS = 8
    const val SUBSAMPLING = 8
    const val CHUNK = 340
    const val RIGHT_CONTEXT = 40
    const val FIFO = 40
    const val UPDATE_PERIOD = 300
    const val CACHE = 264
    const val SILENCE_FRAMES = 1
    const val SCORE_THRESHOLD = 0.25f
    const val LATEST_BOOST = 0.05f
    const val MIN_POSITIVE_RATE = 0.5
    const val STRONG_RATE = 0.75
    const val WEAK_RATE = 1.5
    const val HOP = 160
    const val N_FFT = 512
    const val WIN = 400
    const val MELS = 128
    const val BINS = 257
    const val PREEMPHASIS = 0.97f
    val LOG_GUARD = Math.scalb(1f, -24)
}

/** Log-mel frames on demand, so a long recording never needs a second full-file array. */
class NemotronMel(private val wave: FloatArray, private val filters: FloatArray, hann: FloatArray,
                  private val sampleCount: Int = wave.size, private val final: Boolean = true,
                  private val sampleAt: (Int) -> Float = { wave[it] }) {
    val frames = 1 + sampleCount / NemotronConfig.HOP
    private val window = DoubleArray(NemotronConfig.N_FFT)
    private val cosines = DoubleArray(NemotronConfig.N_FFT / 2) { cos(2 * PI * it / NemotronConfig.N_FFT) }
    private val sines = DoubleArray(NemotronConfig.N_FFT / 2) { sin(2 * PI * it / NemotronConfig.N_FFT) }
    private val re = DoubleArray(NemotronConfig.N_FFT)
    private val im = DoubleArray(NemotronConfig.N_FFT)
    private val power = FloatArray(NemotronConfig.BINS)
    private val starts = IntArray(NemotronConfig.MELS)
    private val ends = IntArray(NemotronConfig.MELS)

    init {
        require(filters.size == NemotronConfig.MELS * NemotronConfig.BINS && hann.size == NemotronConfig.WIN)
        val offset = (NemotronConfig.N_FFT - NemotronConfig.WIN) / 2
        for (i in hann.indices) window[offset + i] = hann[i].toDouble()
        for (m in 0 until NemotronConfig.MELS) {
            val row = m * NemotronConfig.BINS
            var a = 0
            while (a < NemotronConfig.BINS && filters[row + a] == 0f) a++
            var b = NemotronConfig.BINS
            while (b > a && filters[row + b - 1] == 0f) b--
            starts[m] = a
            ends[m] = b
        }
    }

    private fun emphasized(n: Int): Float = when {
        n < 0 || n >= sampleCount -> 0f
        n == 0 -> sampleAt(0)
        else -> sampleAt(n) - NemotronConfig.PREEMPHASIS * sampleAt(n - 1)
    }

    private fun fft() {
        val n = NemotronConfig.N_FFT
        var j = 0
        for (i in 1 until n) {
            var bit = n shr 1
            while (j and bit != 0) { j = j xor bit; bit = bit shr 1 }
            j = j xor bit
            if (i < j) { val t = re[i]; re[i] = re[j]; re[j] = t }
        }
        var size = 2
        while (size <= n) {
            val half = size / 2
            val step = n / size
            var i = 0
            while (i < n) {
                for (k in 0 until half) {
                    val w = k * step
                    val tr = re[i + k + half] * cosines[w] + im[i + k + half] * sines[w]
                    val ti = im[i + k + half] * cosines[w] - re[i + k + half] * sines[w]
                    re[i + k + half] = re[i + k] - tr
                    im[i + k + half] = im[i + k] - ti
                    re[i + k] += tr
                    im[i + k] += ti
                }
                i += size
            }
            size *= 2
        }
    }

    /** Frames [first, first + count) row by row into [out]. The trailing frame stays zero, as in the export. */
    fun write(first: Int, count: Int, out: FloatArray) {
        for (index in 0 until count) {
            val frame = first + index
            val row = index * NemotronConfig.MELS
            if (final && frame == frames - 1) {
                out.fill(0f, row, row + NemotronConfig.MELS)
                continue
            }
            val start = frame * NemotronConfig.HOP - NemotronConfig.N_FFT / 2
            for (o in 0 until NemotronConfig.N_FFT) {
                re[o] = emphasized(start + o) * window[o]
                im[o] = 0.0
            }
            fft()
            for (k in 0 until NemotronConfig.BINS) {
                val magnitude = sqrt((re[k] * re[k] + im[k] * im[k]).toFloat())
                power[k] = magnitude * magnitude
            }
            for (m in 0 until NemotronConfig.MELS) {
                var sum = 0f
                val filter = m * NemotronConfig.BINS
                for (k in starts[m] until ends[m]) sum += filters[filter + k] * power[k]
                out[row + m] = ln(sum + NemotronConfig.LOG_GUARD)
            }
        }
    }
}

/** Arrival-order speaker cache and FIFO, one recording at a time. */
class NemotronSpeakerCache(private val silence: FloatArray,
                           private val fifoCapacity: Int = NemotronConfig.FIFO,
                           private val updatePeriod: Int = NemotronConfig.UPDATE_PERIOD) {
    private val hidden = NemotronConfig.HIDDEN
    private val speakers = NemotronConfig.SPEAKERS
    private val length = NemotronConfig.CACHE
    private val budget = length / speakers - NemotronConfig.SILENCE_FRAMES
    private val minPositive = floor(budget * NemotronConfig.MIN_POSITIVE_RATE).toInt()
    private val strong = floor(budget * NemotronConfig.STRONG_RATE).toInt()
    private val weak = floor(budget * NemotronConfig.WEAK_RATE).toInt()
    private var embeds = FloatArray(length * hidden)
    private var probs = FloatArray(length * speakers)
    private val fifo = FloatArray(fifoCapacity * hidden)
    var cacheFrames = 0
        private set
    var fifoFrames = 0
        private set
    private var compressed = false
    val chronological get() = !compressed

    init { require(silence.size == hidden && fifoCapacity in 1..512 && updatePeriod in 1..512) }

    /** The long-term speaker cache of a finished pass, with an empty FIFO: a second pass over the same audio
     * then starts already knowing every voice, in the same speaker slots. */
    fun warmCopy(): NemotronSpeakerCache = NemotronSpeakerCache(silence, fifoCapacity, updatePeriod).also {
        embeds.copyInto(it.embeds)
        probs.copyInto(it.probs)
        it.cacheFrames = cacheFrames
        it.compressed = compressed
    }

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
        val popped = if (pending <= fifoCapacity) 0 else min(max(updatePeriod, pending - fifoCapacity), pending)
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

/**
 * Turns from per-frame C2 speaker probabilities, after the hysteresis/padding/duration post-processing of
 * docs/C2_POSTPROCESS_2026-11-06.md (team notebook, section 9). Thresholds are probabilities; seconds are seconds.
 * [RAW] reproduces the original decision: a frame is speech when p > 0.5, no smoothing (identical turns at the
 * millisecond resolution DiarizationTimeline.canonicalize keeps).
 */
data class NemotronPostprocess(
    val onset: Float = 0.5f,
    val offset: Float = 0.5f,
    /** Lower onset for a second voice while another speaker is already confidently active. */
    val overlapOnset: Float = onset,
    val padOnSeconds: Float = 0f,
    val padOffSeconds: Float = 0f,
    val minOnSeconds: Float = 0f,
    val minOffSeconds: Float = 0f,
) {
    init {
        require(listOf(onset, offset, overlapOnset).all { it > 0f && it < 1f }) { "Thresholds must be in (0, 1)" }
        require(listOf(padOnSeconds, padOffSeconds, minOnSeconds, minOffSeconds).all { it >= 0f }) { "Negative duration" }
    }

    companion object {
        val RAW = NemotronPostprocess()

        /** Tuned on 27 dev recordings, checked once on 35 speaker-disjoint test recordings
         * (docs/evidence/c2-postprocess-20261106/result.json): test DER 8.59% -> 5.80% (collar 0). */
        val PRODUCT = NemotronPostprocess(onset = 0.45f, offset = 0.3f, overlapOnset = 0.45f,
            padOnSeconds = 0.05f, padOffSeconds = 0.02f, minOnSeconds = 0.24f, minOffSeconds = 0.4f)
    }
}

/** Flattened [frames, SPEAKERS] logits at 10 ms per frame. */
class NemotronFrameLogits(val logits: FloatArray, val frames: Int) {
    val speakers get() = NemotronConfig.SPEAKERS
}

object NemotronDiarizer {
    const val FRAME_SECONDS = 0.01f

    fun diarize(wave: FloatArray, filters: FloatArray, hann: FloatArray, silence: FloatArray, runner: NemotronChunkRunner,
                checkCancelled: () -> Unit = {}, postprocess: NemotronPostprocess = NemotronPostprocess.RAW,
                warmSecondPass: Boolean = false,
                onProgress: (Int, Int) -> Unit = { _, _ -> }): List<ClusterTurn> {
        val mel = { NemotronMel(wave, filters, hann) }
        return if (warmSecondPass) warmGuarded(mel, silence, runner, checkCancelled, postprocess, onProgress)
               else binarize(frameLogitsWithCache(mel, runner, checkCancelled,
                   NemotronSpeakerCache(silence), onProgress).first, postprocess)
    }

    private fun speakerCount(turns: List<ClusterTurn>) = turns.mapTo(HashSet()) { it.cluster }.size

    /**
     * Warm second-pass turns, unless they have fewer speakers than the first pass. On short dialogues the warm
     * cache can absorb a second voice into the first slot (aba.wav, 13 s: A-B-A became A-A-A); falling back keeps
     * the first pass there. Host corpus (docs/C2_POSTPROCESS_2026-11-06.md): dev unchanged, test DER 4.96 -> 5.01 %
     * (one fallback, rec_0517, where warm had lost a speaker), speaker count 91 -> 94 %.
     */
    fun chooseWarm(single: List<ClusterTurn>, warm: List<ClusterTurn>): List<ClusterTurn> =
        if (speakerCount(warm) >= speakerCount(single)) warm else single

    private fun logit(p: Float): Float = if (p == 0.5f) 0f else ln(p / (1f - p))

    /** Same algorithm as tools/c2pp/postprocess.py `binarize`: thresholds in logit space, times in integer ms. */
    fun binarize(frame: NemotronFrameLogits, pp: NemotronPostprocess = NemotronPostprocess.RAW): List<ClusterTurn> {
        val frames = frame.frames
        val speakers = frame.speakers
        val l = frame.logits
        val on = logit(pp.onset)
        val overlapOn = logit(pp.overlapOnset)
        val low = logit(minOf(pp.offset, pp.onset, pp.overlapOnset))
        val confident = IntArray(frames)
        for (t in 0 until frames) for (s in 0 until speakers) if (l[t * speakers + s] > on) confident[t]++
        // Integer milliseconds, so the merge/min-duration comparisons cannot flip on float rounding.
        fun ms(seconds: Float) = Math.round(seconds * 1000.0).toInt()
        val frameMs = ms(FRAME_SECONDS)
        val end = frames * frameMs
        val padOn = ms(pp.padOnSeconds); val padOff = ms(pp.padOffSeconds)
        val minOff = ms(pp.minOffSeconds); val minOn = max(ms(pp.minOnSeconds), 1)
        val turns = mutableListOf<ClusterTurn>()
        for (s in 0 until speakers) {
            val merged = mutableListOf<IntArray>()
            var runStart = -1
            var runHasOnset = false
            for (t in 0..frames) {
                var isLow = false
                var isHigh = false
                if (t < frames) {
                    val v = l[t * speakers + s]
                    val main = v > on
                    val others = confident[t] - if (main) 1 else 0
                    isHigh = if (others > 0) v > overlapOn else main
                    isLow = v > low || isHigh
                }
                if (isLow) {
                    if (runStart < 0) runStart = t
                    if (isHigh) runHasOnset = true
                    continue
                }
                if (runStart >= 0) {
                    if (runHasOnset) {
                        val a = max(0, runStart * frameMs - padOn)
                        val b = min(end, t * frameMs + padOff)
                        val last = merged.lastOrNull()
                        if (last != null && a - last[1] <= minOff) last[1] = max(last[1], b)
                        else merged += intArrayOf(a, b)
                    }
                    runStart = -1
                    runHasOnset = false
                }
            }
            for (seg in merged) if (seg[1] - seg[0] >= minOn) turns += ClusterTurn(seg[0] / 1000f, seg[1] / 1000f, s)
        }
        return turns.sortedWith(compareBy<ClusterTurn> { it.startSeconds }.thenBy { it.cluster })
    }

    /** The offline chunk loop; returns raw logits for every 10 ms frame (positive logit = probability > 0.5). */
    fun frameLogits(wave: FloatArray, filters: FloatArray, hann: FloatArray, silence: FloatArray, runner: NemotronChunkRunner,
                    checkCancelled: () -> Unit = {}): NemotronFrameLogits =
        frameLogitsWithCache({ NemotronMel(wave, filters, hann) }, runner, checkCancelled, NemotronSpeakerCache(silence)).first

    /** Second pass over the same audio, starting from the speaker cache the first pass ended with. */
    fun warmFrameLogits(wave: FloatArray, filters: FloatArray, hann: FloatArray, silence: FloatArray, runner: NemotronChunkRunner,
                        checkCancelled: () -> Unit = {}): NemotronFrameLogits =
        warm({ NemotronMel(wave, filters, hann) }, silence, runner, checkCancelled)

    /**
     * The same offline diarization over audio read through [sampleAt] (e.g. a recording journal on disk),
     * so a long capture never has to be loaded as one array.
     */
    fun diarizeSamples(sampleCount: Int, sampleAt: (Int) -> Float, filters: FloatArray, hann: FloatArray, silence: FloatArray,
                       runner: NemotronChunkRunner, checkCancelled: () -> Unit = {},
                       postprocess: NemotronPostprocess = NemotronPostprocess.RAW, warmSecondPass: Boolean = false): List<ClusterTurn> {
        val mel = { NemotronMel(FloatArray(0), filters, hann, sampleCount, true, sampleAt) }
        return if (warmSecondPass) warmGuarded(mel, silence, runner, checkCancelled, postprocess)
               else binarize(frameLogitsWithCache(mel, runner, checkCancelled, NemotronSpeakerCache(silence)).first, postprocess)
    }

    private fun warmGuarded(mel: () -> NemotronMel, silence: FloatArray, runner: NemotronChunkRunner,
                            checkCancelled: () -> Unit, postprocess: NemotronPostprocess,
                            onProgress: (Int, Int) -> Unit = { _, _ -> }): List<ClusterTurn> {
        // Both passes count as work. The count is actual completed native chunks,
        // never simulated time. Progress must not jump back at warm-pass start.
        var firstChunks = 0
        val first = frameLogitsWithCache(mel, runner, checkCancelled, NemotronSpeakerCache(silence)) { done, total ->
            firstChunks = total
            onProgress(done, total * 2)
        }
        val single = binarize(first.first, postprocess)
        val warm = binarize(frameLogitsWithCache(mel, runner, checkCancelled, first.second.warmCopy()) { done, total ->
            onProgress(firstChunks + done, firstChunks + total)
        }.first, postprocess)
        return chooseWarm(single, warm)
    }

    private fun warm(mel: () -> NemotronMel, silence: FloatArray, runner: NemotronChunkRunner,
                     checkCancelled: () -> Unit): NemotronFrameLogits {
        val first = frameLogitsWithCache(mel, runner, checkCancelled, NemotronSpeakerCache(silence))
        return frameLogitsWithCache(mel, runner, checkCancelled, first.second.warmCopy()).first
    }

    private fun frameLogitsWithCache(newMel: () -> NemotronMel, runner: NemotronChunkRunner, checkCancelled: () -> Unit,
                                     cache: NemotronSpeakerCache,
                                     onProgress: (Int, Int) -> Unit = { _, _ -> }): Pair<NemotronFrameLogits, NemotronSpeakerCache> {
        val mel = newMel()
        val factor = NemotronConfig.SUBSAMPLING
        val melFrames = mel.frames
        val embeddings = (melFrames + factor - 1) / factor
        val valid = max(melFrames - 1, 0)
        val speakers = NemotronConfig.SPEAKERS
        val all = FloatArray(melFrames * speakers)
        var written = 0
        var start = 0
        val totalChunks = (embeddings + NemotronConfig.CHUNK - 1) / NemotronConfig.CHUNK
        while (start < embeddings) {
            checkCancelled()
            val end = min(start + NemotronConfig.CHUNK, embeddings)
            val chunkFrames = end - start
            val melStart = start * factor
            val melEnd = min((end + NemotronConfig.RIGHT_CONTEXT) * factor, melFrames)
            val chunk = FloatArray((melEnd - melStart) * NemotronConfig.MELS)
            mel.write(melStart, melEnd - melStart, chunk)
            val contextFrames = cache.contextFrames()
            val step = runner.run(chunk, melEnd - melStart, max(min(melEnd, valid) - melStart, 0), cache.context(), contextFrames)
            cache.update(step, chunkFrames)
            val from = contextFrames * factor
            val until = min((contextFrames + chunkFrames) * factor, from + (melFrames - written))
            for (row in from until until) {
                System.arraycopy(step.logits, row * speakers, all, written * speakers, speakers)
                written++
            }
            start = end
            onProgress((end + NemotronConfig.CHUNK - 1) / NemotronConfig.CHUNK, totalChunks)
        }
        return NemotronFrameLogits(if (written == melFrames) all else all.copyOf(written * speakers), written) to cache
    }
}
