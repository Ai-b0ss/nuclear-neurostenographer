// SPDX-License-Identifier: LicenseRef-OpenMDW-1.1
// Port of diarize.py from joosthel/Nemotron-3-Diarization-ONNX (Copyright 2026 Joost Helfers),
// revision 4a911fc3ca821b76a99fffd5ce5135bd1efca540. See docs/NEMOTRON_ANDROID.md.
package ru.neurostenographer.core

import kotlin.math.PI
import kotlin.math.cos
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

/** Log-mel frames on demand, so a long recording never needs a second full-file array. */
class NemotronMel(private val wave: FloatArray, private val filters: FloatArray, hann: FloatArray) {
    private val hannCoefficients = hann.copyOf()
    val frames = 1 + wave.size / NemotronConfig.HOP
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
        n < 0 || n >= wave.size -> 0f
        n == 0 -> wave[0]
        else -> wave[n] - NemotronConfig.PREEMPHASIS * wave[n - 1]
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
    fun write(first: Int, count: Int, out: FloatArray) =
        NativeNemotronMel.write(wave, filters, hannCoefficients, first, count, out)

    /** Reference path retained for paired numerical checks during the C++ port. */
    fun writeReference(first: Int, count: Int, out: FloatArray) {
        for (index in 0 until count) {
            val frame = first + index
            val row = index * NemotronConfig.MELS
            if (frame == frames - 1) {
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

object NemotronDiarizer {
    /** The offline chunk loop. Frames count as speech when the logit is positive, the same as probability > 0.5. */
    fun diarize(wave: FloatArray, filters: FloatArray, hann: FloatArray, silence: FloatArray, runner: NemotronChunkRunner,
                checkCancelled: () -> Unit = {}): List<ClusterTurn> {
        val mel = NemotronMel(wave, filters, hann)
        val factor = NemotronConfig.SUBSAMPLING
        val melFrames = mel.frames
        val embeddings = (melFrames + factor - 1) / factor
        val valid = max(melFrames - 1, 0)
        val cache = NativeNemotronSpeakerCache(silence)
        val speakers = NemotronConfig.SPEAKERS
        val opened = IntArray(speakers) { -1 }
        val turns = mutableListOf<ClusterTurn>()
        var written = 0
        var start = 0
        try {
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
                for (s in 0 until speakers) {
                    val active = step.logits[row * speakers + s] > 0f
                    if (active && opened[s] < 0) opened[s] = written
                    if (!active && opened[s] >= 0) {
                        turns += ClusterTurn(opened[s] * 0.01f, written * 0.01f, s)
                        opened[s] = -1
                    }
                }
                written++
            }
            start = end
            }
        } finally { cache.close() }
        for (s in 0 until speakers) if (opened[s] >= 0) turns += ClusterTurn(opened[s] * 0.01f, written * 0.01f, s)
        return turns.sortedWith(compareBy<ClusterTurn> { it.startSeconds }.thenBy { it.cluster })
    }
}
