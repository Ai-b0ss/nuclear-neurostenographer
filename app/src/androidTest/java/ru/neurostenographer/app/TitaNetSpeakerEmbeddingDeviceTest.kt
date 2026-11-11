package ru.neurostenographer.app

import android.os.SystemClock
import android.util.Log
import androidx.test.platform.app.InstrumentationRegistry
import com.k2fsa.sherpa.onnx.SpeakerEmbeddingExtractor
import com.k2fsa.sherpa.onnx.SpeakerEmbeddingExtractorConfig
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import ru.neurostenographer.core.PcmWav
import java.io.File
import kotlin.math.sqrt

/**
 * Model smoke + diagnostic cosine matrix on HONOR.
 * QA inputs remain on the device, never bundled or uploaded.
 * Two audio sources have no independently verified human identity ground truth:
 * this test is NOT a released diarization accuracy score.
 */
class TitaNetSpeakerEmbeddingDeviceTest {
    private val inst = InstrumentationRegistry.getInstrumentation()

    @Test fun modelRunsAndProducesFiniteDiscriminativeEmbeddings() {
        val target = inst.targetContext
        assumeTrue("Only the isolated QA build is allowed to load test models",
            BuildConfig.GLOBAL_SPEAKER_BOOK)
        val dir = File(requireNotNull(target.getExternalFilesDir("qa")), "titanet")
        val modelFile = File(dir, "nemo_en_titanet_small.onnx")
        val firstFile = File(dir, "01_ru_two_speakers_slow.wav")
        val secondFile = File(dir, "05_ru_truecrime_three_speakers_natural.wav")
        assumeTrue("Push exact vetted public artifacts into own QA directory first",
            modelFile.isFile && firstFile.isFile && secondFile.isFile)
        val report = File(target.filesDir, "titanet-device-evidence.json")
        val began = SystemClock.elapsedRealtime()

        val first = firstFile.inputStream().use { PcmWav.read(it).samples }
        val second = secondFile.inputStream().use { PcmWav.read(it).samples }
        fun cut(wave: FloatArray, from: Int, to: Int): FloatArray {
            val a = from * 16000
            val b = to * 16000
            check(a >= 0 && b <= wave.size && b > a)
            return wave.copyOfRange(a, b)
        }
        fun cosine(a: FloatArray, b: FloatArray): Double {
            require(a.size == b.size && a.isNotEmpty())
            var dot = 0.0
            var a2 = 0.0
            var b2 = 0.0
            for (i in a.indices) {
                dot += a[i].toDouble() * b[i]
                a2 += a[i].toDouble() * a[i]
                b2 += b[i].toDouble() * b[i]
            }
            return dot / sqrt(a2 * b2)
        }

        val extractor = SpeakerEmbeddingExtractor(
            config = SpeakerEmbeddingExtractorConfig(
                model = modelFile.absolutePath, numThreads = 2, debug = false, provider = "cpu"))
        try {
            fun embed(pcm: FloatArray): FloatArray {
                val stream = extractor.createStream()
                try {
                    stream.acceptWaveform(pcm, 16000)
                    stream.inputFinished()
                    assertTrue("TitaNet cannot extract speaker embedding", extractor.isReady(stream))
                    return extractor.compute(stream).also { values ->
                        assertEquals("TitaNet extractor dimension", extractor.dim(), values.size)
                        assertTrue(values.size in 64..2048)
                        assertTrue("NaN or infinite embedding", values.all { it.isFinite() })
                    }
                } finally {
                    stream.release()
                }
            }
            val voiceA = cut(first, 2, 12)
            val gain = FloatArray(voiceA.size) { i -> voiceA[i] * 0.94f }
            val clips = linkedMapOf(
                "first_speaker_a" to voiceA,
                "same_speaker_gain94" to gain,
                "first_speaker_a_later_utterance" to cut(first, 59, 67),
                "first_speaker_b" to cut(first, 24, 34),
                "other_source_speaker_a" to cut(second, 85, 93),
                "other_source_speaker_b" to cut(second, 26, 36))
            val vectors = clips.mapValues { (_, wave) -> embed(wave) }
            val matrix = JSONObject()
            val names = clips.keys.toList()
            for (a in names.indices) {
                val pairs = JSONObject()
                for (b in names.indices) {
                    pairs.put(names[b], cosine(requireNotNull(vectors[names[a]]),
                        requireNotNull(vectors[names[b]])))
                }
                matrix.put(names[a], pairs)
            }
            val evidence = JSONObject()
                .put("scope", "titanet_small_6_slices_from_two_unannotated_audio_sources")
                .put("model", "nemo_en_titanet_small.onnx")
                .put("embedding_dim", extractor.dim())
                .put("pairwise_cosine", matrix)
                .put("wall_ms", SystemClock.elapsedRealtime() - began)
                .put("note", "Same source repeated gain is a positive control; cross-source IDs not human validated")
            report.writeText(evidence.toString(2))
            Log.i("TitaNetDeviceQA", evidence.toString())
            val sameScore = cosine(requireNotNull(vectors["first_speaker_a"]),
                requireNotNull(vectors["same_speaker_gain94"]))
            val crossScore = cosine(requireNotNull(vectors["first_speaker_a"]),
                requireNotNull(vectors["other_source_speaker_a"]))
            val laterScore = cosine(requireNotNull(vectors["first_speaker_a"]),
                requireNotNull(vectors["first_speaker_a_later_utterance"]))
            assertTrue("Identical waveform with gain adjustment should be more similar than different-source clip",
                sameScore > crossScore)
            // Independent utterance from C2's same local speaker in this test clip.
            // Not a separately human-verified identity label.
            assertTrue("Later utterance should be closer than another speaker in same source",
                laterScore > cosine(requireNotNull(vectors["first_speaker_a"]),
                    requireNotNull(vectors["first_speaker_b"])))
        } finally {
            extractor.release()
        }
    }
}
