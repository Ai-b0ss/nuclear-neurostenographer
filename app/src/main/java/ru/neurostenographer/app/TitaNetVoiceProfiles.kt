package ru.neurostenographer.app

import android.content.Context
import com.k2fsa.sherpa.onnx.SpeakerEmbeddingExtractor
import com.k2fsa.sherpa.onnx.SpeakerEmbeddingExtractorConfig
import ru.neurostenographer.core.PcmAudio
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
    private const val MAX_VOICE_MS = 16000L
    private const val MIN_VOICE_MS = 3000L

    fun compute(context: Context, audio: PcmAudio, turns: List<SpeakerTurn>): List<VoicePrint> {
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

        val speakers = turns.filter { it.attributionEligible }
            .map { it.speakerId }.distinct()
        if (speakers.isEmpty() || speakers.size > 8) return emptyList()
        val frames = (audio.samples.size / SAMPLE_PER_HOP)
        if (frames == 0 || frames > 30000) return emptyList()

        // A 40 ms frame must be fully covered by exactly ONE C2 speaker.
        // Partially covered frames and overlaps never become voice evidence.
        val owners = IntArray(frames) { -1 }
        val idToIndex = speakers.withIndex().associate { it.value to it.index }
        for (t in turns) {
            if (!t.attributionEligible || t.endMs > audio.durationMs) continue
            val id = idToIndex[t.speakerId] ?: continue
            val start = ((t.startMs + HOP_MS - 1) / HOP_MS).toInt().coerceIn(0, frames)
            val end = (t.endMs / HOP_MS).toInt().coerceIn(0, frames)
            for (i in start until end) {
                if (owners[i] == -1) owners[i] = id
                else if (owners[i] != id) owners[i] = -2
            }
        }
        val sampleLimit = MAX_VOICE_MS.toInt() * RATE / 1000
        val signal = Array(speakers.size) { FloatArray(sampleLimit) }
        val count = IntArray(speakers.size)
        for (frame in owners.indices) {
            val id = owners[frame]
            if (id !in speakers.indices || count[id] + SAMPLE_PER_HOP > sampleLimit) continue
            val offset = frame * SAMPLE_PER_HOP
            audio.samples.copyInto(signal[id], count[id], offset, offset + SAMPLE_PER_HOP)
            count[id] += SAMPLE_PER_HOP
        }
        val eligible = speakers.indices.filter {
            count[it] >= MIN_VOICE_MS.toInt() * RATE / 1000
        }
        if (eligible.isEmpty()) return emptyList()
        val extractor = SpeakerEmbeddingExtractor(config = SpeakerEmbeddingExtractorConfig(
            model = model.absolutePath, numThreads = 2, debug = false, provider = "cpu"))
        try {
            require(extractor.dim() == DIM) { "Unexpected TitaNet dimension" }
            return eligible.mapNotNull { id ->
                val stream = extractor.createStream()
                try {
                    val pcm = signal[id].copyOf(count[id])
                    stream.acceptWaveform(pcm, RATE)
                    stream.inputFinished()
                    if (!extractor.isReady(stream)) return@mapNotNull null
                    val emb = extractor.compute(stream)
                    if (emb.size != DIM || emb.any { !it.isFinite() }) return@mapNotNull null
                    VoicePrint(speakers[id], emb, count[id].toLong() * 1000 / RATE)
                } finally {
                    stream.release()
                }
            }
        } finally {
            extractor.release()
        }
    }
}
