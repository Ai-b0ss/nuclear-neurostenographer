package ru.neurostenographer.app

import com.k2fsa.sherpa.onnx.*
import ru.neurostenographer.core.*
import java.io.File

data class AsrOutput(val segments: List<TranscriptSegment>, val audioMs: Long,
    val loadMs: Long, val decodeMs: Long, val decodedWindows: Int = 0)

/** Owns native resources on one worker. Fragment times are input windows, not word alignments. */
object OfflineAsr {
    fun transcribe(audio: PcmAudio, model: File, checkCancelled: () -> Unit = {},
                   progress: (Int, Int) -> Unit = { _, _ -> },
                   turns: List<SpeakerTurn> = emptyList(),
                   speechWindows: List<AudioWindow>? = null): AsrOutput {
        require(audio.sampleRate == 16000 && audio.samples.size >= 1600 &&
            audio.samples.size <= PcmWav.MAX_SECONDS * 16000) { "Аудио должно длиться от 0,1 до 120 секунд" }
        val windows = speechWindows ?: DiarizationTimeline.windows(turns, audio.durationMs)
        require(windows.all { it.startMs >= 0 && it.endMs <= audio.durationMs && it.endMs - it.startMs in 100..20_000 } &&
            windows.zipWithNext().all { (a, b) -> a.endMs <= b.startMs }) { "Invalid ASR input windows" }
        checkCancelled()
        if (windows.isEmpty()) return AsrOutput(emptyList(), audio.durationMs, 0, 0)
        val started = System.nanoTime()
        val recognizer = OfflineRecognizer(config = OfflineRecognizerConfig(
            featConfig = FeatureConfig(sampleRate = 16000, featureDim = 64),
            modelConfig = OfflineModelConfig(
                nemo = OfflineNemoEncDecCtcModelConfig(model = File(model, "model.int8.onnx").absolutePath),
                tokens = File(model, "tokens.txt").absolutePath,
                numThreads = 2, provider = "cpu", debug = false
            ), decodingMethod = "greedy_search"
        ))
        val loaded = System.nanoTime()
        val chunks = mutableListOf<RecognizedChunk>()
        try {
            // Bound Conformer attention memory; cutting words at boundaries is a known baseline limitation.
            val total = windows.size
            for (index in 0 until total) {
                checkCancelled()
                progress(index + 1, total)
                val start = (windows[index].startMs * 16).toInt()
                val end = minOf((windows[index].endMs * 16).toInt(), audio.samples.size)
                val stream = recognizer.createStream()
                try {
                    // A short final fragment still needs enough frames for convolution subsampling.
                    val samples = audio.samples.copyOfRange(start, end)
                    stream.acceptWaveform(if (samples.size < 16000) samples.copyOf(16000) else samples, 16000)
                    recognizer.decode(stream)
                    checkCancelled()
                    val text = recognizer.getResult(stream).text.trim()
                    if (text.isNotBlank()) chunks += RecognizedChunk(
                        start * 1000L / 16000, maxOf(start * 1000L / 16000 + 1, end * 1000L / 16000), text)
                } finally { stream.release() }
            }
        } finally { recognizer.release() }
        return AsrOutput(TranscriptFusion.attributeChunks(chunks, turns), audio.durationMs,
            (loaded - started) / 1_000_000, (System.nanoTime() - loaded) / 1_000_000, windows.size)
    }
}
