package ru.neurostenographer.app

import com.k2fsa.sherpa.onnx.*
import ru.neurostenographer.core.*
import java.io.File

data class EnglishAsrOutput(val segments: List<TranscriptSegment>, val loadMs: Long,
    val decodeMs: Long, val windows: Int)

/** Uses Whisper's language token, never spelling/script heuristics. Models are released
 * before the Russian A3 is loaded; this does not replace the Russian recognizer. */
object WhisperEnglish {
    const val ID = "sherpa-onnx-1.12.20/whisper-tiny-int8-en"
    const val REVISION = "csukuangfj/sherpa-onnx-whisper-tiny@65176e2deb88badc814a94058666cadccc29b61c"

    fun detect(audio: PcmAudio, model: File, windows: List<AudioWindow>,
               checkCancelled: () -> Unit = {}): String? {
        require(audio.sampleRate == 16000)
        val parts = windows.filter { it.endMs - it.startMs >= 300 }.take(12)
        val sample = FloatArray(minOf(15 * 16000,
            parts.sumOf { ((it.endMs - it.startMs) * 16).toInt() }))
        var size = 0
        for (part in parts) {
            checkCancelled()
            require(part.startMs >= 0 && part.endMs <= audio.durationMs)
            val count = minOf(((part.endMs - part.startMs) * 16).toInt(), sample.size - size)
            audio.samples.copyInto(sample, size, (part.startMs * 16).toInt(), (part.startMs * 16).toInt() + count)
            size += count
            if (size == sample.size) break
        }
        if (size < 4800 || sample.all { it == 0f }) return null
        val detector = SpokenLanguageIdentification(config = SpokenLanguageIdentificationConfig(
            whisper = SpokenLanguageIdentificationWhisperConfig(
                encoder = File(model, "tiny-encoder.int8.onnx").absolutePath,
                decoder = File(model, "tiny-decoder.int8.onnx").absolutePath),
            numThreads = InferenceThreads.count(), provider = "cpu"))
        try {
            val stream = detector.createStream()
            try {
                stream.acceptWaveform(sample, 16000)
                checkCancelled()
                val language = detector.compute(stream)
                checkCancelled()
                return language
            } finally { stream.release() }
        } finally { detector.release() }
    }

    fun transcribe(audio: PcmAudio, model: File, turns: List<SpeakerTurn>,
                   speechWindows: List<AudioWindow>?, checkCancelled: () -> Unit = {},
                   progress: (Int, Int) -> Unit = { _, _ -> }): EnglishAsrOutput {
        // Whisper does not supply A3's word-emission timestamps. Preserve real turn
        // boundaries and conservative attribution instead of fabricating word times.
        val windows = QuietCuts.refine(if (speechWindows != null)
            DiarizationTimeline.turnWindows(turns, audio.durationMs)
        else DiarizationTimeline.windows(turns, audio.durationMs), audio.samples)
        if (windows.isEmpty()) return EnglishAsrOutput(emptyList(), 0, 0, 0)
        val started = System.nanoTime()
        val recognizer = OfflineRecognizer(config = OfflineRecognizerConfig(
            featConfig = FeatureConfig(sampleRate = 16000, featureDim = 80),
            modelConfig = OfflineModelConfig(
                whisper = OfflineWhisperModelConfig(
                    encoder = File(model, "tiny-encoder.int8.onnx").absolutePath,
                    decoder = File(model, "tiny-decoder.int8.onnx").absolutePath,
                    language = "en", task = "transcribe"),
                tokens = File(model, "tiny-tokens.txt").absolutePath,
                numThreads = InferenceThreads.count(), provider = "cpu"),
            decodingMethod = "greedy_search"))
        val loaded = System.nanoTime()
        val chunks = mutableListOf<RecognizedChunk>()
        try {
            windows.forEachIndexed { index, window ->
                checkCancelled()
                progress(index + 1, windows.size)
                val samples = audio.samples.copyOfRange((window.startMs * 16).toInt(), (window.endMs * 16).toInt())
                // Do not ask a generative decoder to transcribe digital silence.
                if (samples.all { it == 0f }) return@forEachIndexed
                val stream = recognizer.createStream()
                try {
                    stream.acceptWaveform(samples, 16000)
                    recognizer.decode(stream)
                    checkCancelled()
                    val text = recognizer.getResult(stream).text.trim()
                    if (text.isNotEmpty()) chunks += RecognizedChunk(window.startMs, window.endMs, text)
                } finally { stream.release() }
            }
        } finally { recognizer.release() }
        return EnglishAsrOutput(TranscriptFusion.mergeReplies(TranscriptFusion.attributeChunks(chunks, turns)),
            (loaded - started) / 1_000_000, (System.nanoTime() - loaded) / 1_000_000, windows.size)
    }
}
