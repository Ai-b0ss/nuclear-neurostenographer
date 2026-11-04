package ru.neurostenographer.app

import androidx.test.platform.app.InstrumentationRegistry
import com.k2fsa.sherpa.onnx.FeatureConfig
import com.k2fsa.sherpa.onnx.OfflineModelConfig
import com.k2fsa.sherpa.onnx.OfflineNemoEncDecCtcModelConfig
import com.k2fsa.sherpa.onnx.OfflineRecognizer
import com.k2fsa.sherpa.onnx.OfflineRecognizerConfig
import org.junit.Assert.assertEquals
import org.junit.Test
import ru.neurostenographer.core.PcmWav
import java.io.File

class NativeAsrProbeTest {
    @Test fun nativeCapiMatchesPinnedJniOnSameWaveform() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val model = instrumentation.context.assets.open("gigaam-v3.zip").use {
            AsrModelStore(instrumentation.targetContext).install(it)
        }
        val audio = instrumentation.context.assets.open("nemotron-bench/acted-dmd.wav").use { PcmWav.read(it) }
        val samples = audio.samples
        val threads = InferenceThreads.count()
        val config = OfflineRecognizerConfig(
            featConfig = FeatureConfig(sampleRate = 16000, featureDim = 64),
            modelConfig = OfflineModelConfig(
                nemo = OfflineNemoEncDecCtcModelConfig(File(model, "model.int8.onnx").absolutePath),
                tokens = File(model, "tokens.txt").absolutePath,
                numThreads = threads, provider = "cpu", debug = false),
            decodingMethod = "greedy_search")
        val recognizer = OfflineRecognizer(config = config)
        val stream = recognizer.createStream()
        val expected: String
        try {
            stream.acceptWaveform(samples, 16000)
            recognizer.decode(stream)
            expected = recognizer.getResult(stream).text.trim()
        } finally {
            stream.release()
            recognizer.release()
        }
        assertEquals(expected, NativeAsrProbe.recognize(samples, model.absolutePath, threads).trim())
    }
}
