package ru.neurostenographer.app

import android.content.Context
import com.k2fsa.sherpa.onnx.SpeakerEmbeddingExtractor
import com.k2fsa.sherpa.onnx.SpeakerEmbeddingExtractorConfig
import ru.neurostenographer.core.PcmAudio
import ru.neurostenographer.core.CleanSpeakerFrames
import ru.neurostenographer.core.VoicePrintAgreement
import ru.neurostenographer.core.SpeakerTurn
import ru.neurostenographer.core.VoicePrint
import java.io.File
import java.security.MessageDigest

/**
 * Independent speaker-verification embeddings for experimental cross-window linkage.
 * The 192-dimensional TitaNet speaker model is intentionally NOT the 512-dimensional
 * C2 diarization encoder (which produced possible false merges on held-out sources).
 * An absent or invalid model fails CLOSED: per-block speaker labels are preserved.
 */
object TitaNetVoiceProfiles {
    const val DIM = 192
    private const val SHA256 = "ad4a1802485d8b34c722d2a9d04249662f2ece5d28a7a039063ca22f515a789e"
    private const val SIZE = 40_257_283L
    private const val HOP_MS = 40
    private const val RATE = 16000
    private const val SAMPLE_PER_HOP = RATE * HOP_MS / 1000
    private const val MIN_VOICE_MS = 3000L

    fun compute(context: Context, audio: PcmAudio, turns: List<SpeakerTurn>): List<VoicePrint> {
        return computeForBudget(context, audio, turns, 16000)
    }

    /** Internal fixed-budget comparison for QA; both paths retain all safety gates. */
    internal fun computeForBudget(context: Context, audio: PcmAudio,
                                  turns: List<SpeakerTurn>, maxSampleMs: Int): List<VoicePrint> {
        require(maxSampleMs == 8000 || maxSampleMs == 16000)
        if (!BuildConfig.GLOBAL_SPEAKER_BOOK || audio.sampleRate != RATE) return emptyList()
        val qa = context.getExternalFilesDir("qa") ?: return emptyList()
        val allowed = File(qa, "titanet").canonicalFile
        val model = File(allowed, "nemo_en_titanet_small.onnx").canonicalFile
        if (model.parentFile != allowed || !model.isFile || model.length() != SIZE) return emptyList()
        val hash = MessageDigest.getInstance("SHA-256")
        model.inputStream().buffered().use { stream ->
            val buf = ByteArray(65536)
            while (true) {
                val n = stream.read(buf)
                if (n < 0) break
                hash.update(buf, 0, n)
            }
        }
        if (hash.digest().joinToString("") { "%02x".format(it.toInt() and 0xff) } != SHA256) return emptyList()

        val frames = (audio.samples.size / SAMPLE_PER_HOP)
        if (frames == 0 || frames > 30000) return emptyList()

        // Compute evidence from all turns, not just eligible ones: an
        // ineligible/unknown overlapping turn must block its contaminated
        // samples even when it is excluded from voice attribution.
        val selection = CleanSpeakerFrames.select(turns, frames, audio.durationMs, HOP_MS)
        val speakers = selection.speakerIds
        if (speakers.isEmpty()) return emptyList()
        val owners = selection.owners
        // Require two separate temporal samples, each at least 3 seconds.
        // Samples now allow 16 seconds EACH; they remain temporally disjoint.
        // Sampling a single prefix alone could authorize misattribution
        // of an unrelated speaker incorrectly reusing C2's slot later.
        val plans = speakers.indices.mapNotNull { index ->
            CleanSpeakerFrames.separate(owners, index,
                minFramesPerSample = (MIN_VOICE_MS / HOP_MS).toInt(),
                maxFramesPerSample = maxSampleMs / HOP_MS)
                ?.let { index to it }
        }
        if (plans.isEmpty()) return emptyList()
        val extractor = SpeakerEmbeddingExtractor(config = SpeakerEmbeddingExtractorConfig(
            model = model.absolutePath, numThreads = 2, debug = false, provider = "cpu"))
        try {
            require(extractor.dim() == DIM) { "Unexpected TitaNet dimension" }
            fun embedding(frames: IntArray): FloatArray? {
                val pcm = FloatArray(frames.size * SAMPLE_PER_HOP)
                frames.forEachIndexed { i, frame ->
                    val offset = frame * SAMPLE_PER_HOP
                    audio.samples.copyInto(pcm, i * SAMPLE_PER_HOP,
                        offset, offset + SAMPLE_PER_HOP)
                }
                val stream = extractor.createStream()
                try {
                    stream.acceptWaveform(pcm, RATE)
                    stream.inputFinished()
                    if (!extractor.isReady(stream)) return null
                    return extractor.compute(stream).takeIf {
                        it.size == DIM && it.all { value -> value.isFinite() }
                    }
                } finally {
                    stream.release()
                }
            }
            return plans.mapNotNull { (index, parts) ->
                val early = embedding(parts.early) ?: return@mapNotNull null
                val late = embedding(parts.late) ?: return@mapNotNull null
                // Construction only, NOT identity admission. The book receives both
                // raw samples and rechecks .84 agreement before any enrollment.
                // A disagreement can only reuse an independently verified old anchor.
                val agreed = VoicePrintAgreement.mergeIfConsistent(early, late, minCosine = 0.0)
                    ?: return@mapNotNull null
                VoicePrint(speakers[index], agreed,
                    (parts.early.size + parts.late.size).toLong() * HOP_MS, early, late,
                    parts.early.size.toLong() * HOP_MS, parts.late.size.toLong() * HOP_MS)
            }
        } finally {
            extractor.release()
        }
    }
}
