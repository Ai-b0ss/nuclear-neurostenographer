package ru.neurostenographer.app

import com.k2fsa.sherpa.onnx.*
import ru.neurostenographer.core.*
import java.io.File

data class DiarizationOutput(val turns: List<SpeakerTurn>, val loadMs: Long, val processMs: Long,
    val windows: List<AudioWindow>)

/** One full-recording call: pyannote segmentation, ERes2Net embeddings and
 * complete-link cosine clustering. Threshold is experimental, not confidence.
 */
object OfflineDiarization {
    const val THRESHOLD = 0.9f
    // Do not tune the user's runtime on one tiny acted fixture. The override is
    // strictly for debug-only independent measurements on identical recordings.
    fun validThreshold(value: Float): Boolean = value.isFinite() && value in 0.30f..0.95f
    fun process(audio: PcmAudio, model: File, checkCancelled: () -> Unit = {},
                progress: (Int, Int) -> Unit = { _, _ -> },
                clusteringThreshold: Float = THRESHOLD): DiarizationOutput {
        require(validThreshold(clusteringThreshold)) { "Invalid speaker clustering threshold" }
        require(audio.sampleRate == 16000 && audio.samples.size in 1600..(120 * 16000))
        require(audio.samples.all { it.isFinite() && it in -1f..1f })
        checkCancelled()
        val started = System.nanoTime()
        val engine = OfflineSpeakerDiarization(config = OfflineSpeakerDiarizationConfig(
            segmentation = OfflineSpeakerSegmentationModelConfig(
                pyannote = OfflineSpeakerSegmentationPyannoteModelConfig(File(model, "segmentation.onnx").absolutePath),
                numThreads = 2, provider = "cpu", debug = false),
            embedding = SpeakerEmbeddingExtractorConfig(
                model = File(model, "embedding.onnx").absolutePath, numThreads = 2, provider = "cpu", debug = false),
            clustering = FastClusteringConfig(numClusters = -1, threshold = clusteringThreshold),
            minDurationOn = 0.2f, minDurationOff = 0.0f
        ))
        val loaded = System.nanoTime()
        try {
            check(engine.sampleRate() == audio.sampleRate)
            checkCancelled()
            // v1.12.20 bypasses embeddings/clustering for <=10 s (one window).
            // Zero-pad short recordings past that shortcut; clip output back below.
            val input = if (audio.samples.size <= 160000) audio.samples.copyOf(176000) else audio.samples
            // Do not throw through a native callback. JNI decode is uninterruptible;
            // cancellation is checked before/after and no partial result is published.
            val raw = engine.process(input)
            checkCancelled()
            progress(1, 1)
            val intervals = raw.map { ClusterTurn(it.start, it.end, it.speaker) }
            val turns = DiarizationTimeline.canonicalize(intervals, audio.durationMs)
            return DiarizationOutput(turns, (loaded - started) / 1_000_000,
                (System.nanoTime() - loaded) / 1_000_000,
                DiarizationTimeline.speechWindows(intervals, audio.durationMs))
        } finally { engine.release() }
    }
}
