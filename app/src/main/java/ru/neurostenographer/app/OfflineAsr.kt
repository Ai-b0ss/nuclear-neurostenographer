package ru.neurostenographer.app

import com.k2fsa.sherpa.onnx.*
import ru.neurostenographer.core.*
import java.io.File

data class AsrOutput(val segments: List<TranscriptSegment>, val audioMs: Long,
    val loadMs: Long, val decodeMs: Long, val decodedWindows: Int = 0, val tokenTimedWindows: Int = 0, val untimedWindows: Int = 0)

/** Owns native resources on one worker. With speaker turns, windows follow continuous speech and each
 * word is attributed by its own token timestamps; a window without usable timestamps (and the
 * no-diarization path) keeps input-window times and conservative chunk attribution. */
object OfflineAsr {
    /** CTC (nemo) or NeMo RNNT (transducer); feature settings come from the model metadata in both cases. */
    fun modelConfig(spec: AsrModelSpec, model: File): OfflineModelConfig {
        fun path(name: String?) = File(model, requireNotNull(name)).absolutePath
        return if (spec.ctcModel != null) OfflineModelConfig(
            nemo = OfflineNemoEncDecCtcModelConfig(model = path(spec.ctcModel)), tokens = path(spec.tokens),
            numThreads = InferenceThreads.count(), provider = "cpu", debug = false)
        else OfflineModelConfig(
            transducer = OfflineTransducerModelConfig(encoder = path(spec.encoder), decoder = path(spec.decoder), joiner = path(spec.joiner)),
            tokens = path(spec.tokens), modelType = "nemo_transducer",
            numThreads = InferenceThreads.count(), provider = "cpu", debug = false)
    }

    fun transcribe(audio: PcmAudio, model: File, checkCancelled: () -> Unit = {},
                   progress: (Int, Int) -> Unit = { _, _ -> },
                   turns: List<SpeakerTurn> = emptyList(),
                   speechWindows: List<AudioWindow>? = null): AsrOutput {
        require(audio.sampleRate == 16000 && audio.samples.size >= 1600 &&
            audio.samples.size <= PcmWav.MAX_SECONDS * 16000) { "Аудио должно длиться от 0,1 секунды до ${PcmWav.MAX_LABEL}" }
        // Token timing is measured for the A3 transducer only (docs/ASR_WORD_ATTRIBUTION_2026-11-05.md);
        // the CTC build keeps cutting at speaker turns and attributing whole fragments.
        val wordTimed = AsrModelSpec.ACTIVE.ctcModel == null
        val windows = QuietCuts.refine(when {
            speechWindows == null -> DiarizationTimeline.windows(turns, audio.durationMs)
            wordTimed -> speechWindows
            else -> DiarizationTimeline.turnWindows(turns, audio.durationMs)
        }, audio.samples)
        require(windows.all { it.startMs >= 0 && it.endMs <= audio.durationMs && it.endMs - it.startMs in 100..20_000 } &&
            windows.zipWithNext().all { (a, b) -> a.endMs <= b.startMs }) { "Invalid ASR input windows" }
        checkCancelled()
        if (windows.isEmpty()) return AsrOutput(emptyList(), audio.durationMs, 0, 0)
        val started = System.nanoTime()
        val recognizer = OfflineRecognizer(config = OfflineRecognizerConfig(
            featConfig = FeatureConfig(sampleRate = 16000, featureDim = 64),
            modelConfig = modelConfig(AsrModelSpec.ACTIVE, model), decodingMethod = "greedy_search"
        ))
        val loaded = System.nanoTime()
        val chunks = mutableListOf<RecognizedChunk>()
        val words = mutableListOf<RecognizedWord>()
        var timed = 0
        try {
            // Bound Conformer attention memory: windows are at most ~22 s, cut at the quietest moment.
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
                    val result = recognizer.getResult(stream)
                    val text = result.text.trim()
                    val startMs = start * 1000L / 16000
                    val endMs = maxOf(startMs + 1, end * 1000L / 16000)
                    val tokenWords = if (turns.isEmpty() || text.isBlank() || !wordTimed) null
                        else TokenWords.words(result.tokens, result.timestamps, startMs, endMs)?.takeIf { it.isNotEmpty() }
                    if (tokenWords != null) { words += tokenWords; timed++ }
                    else if (text.isNotBlank()) chunks += RecognizedChunk(startMs, endMs, text)
                } finally { stream.release() }
            }
        } finally { recognizer.release() }
        val segments = (TranscriptFusion.attributeWords(words, turns) + TranscriptFusion.attributeChunks(chunks, turns))
            .sortedBy { it.startMs }
        return AsrOutput(TranscriptFusion.mergeReplies(segments), audio.durationMs,
            (loaded - started) / 1_000_000, (System.nanoTime() - loaded) / 1_000_000, windows.size, timed, chunks.size)
    }
}
