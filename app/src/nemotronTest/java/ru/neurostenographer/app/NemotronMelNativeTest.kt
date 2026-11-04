package ru.neurostenographer.app

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import android.os.Build
import org.junit.Assert.assertEquals
import org.json.JSONObject
import org.junit.Test
import org.junit.runner.RunWith
import ru.neurostenographer.core.NemotronConfig
import ru.neurostenographer.core.NemotronMel
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.sin

@RunWith(AndroidJUnit4::class)
class NemotronMelNativeTest {
    @Test fun nativeMatchesPinnedModelCoefficients() {
        val assets = InstrumentationRegistry.getInstrumentation().context.assets
        fun floats(name: String, count: Int): FloatArray {
            val bytes = assets.open(name).use { it.readBytes() }
            assertEquals(count * 4, bytes.size)
            return FloatArray(count).also {
                ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(it)
            }
        }
        val wave = FloatArray(16000 * 3 + 37) { sin(it * 0.027).toFloat() * 0.3f }
        val mel = NemotronMel(wave,
            floats("mel_filters.bin", NemotronConfig.MELS * NemotronConfig.BINS),
            floats("hann400.bin", NemotronConfig.WIN))
        val native = FloatArray(300 * NemotronConfig.MELS)
        val reference = FloatArray(native.size)
        mel.write(0, 300, native)
        mel.writeReference(0, 300, reference)
        for (i in native.indices) assertEquals("index=$i", reference[i], native[i], 0.0002f)
    }

    @Test fun nativeMelMatchesPinnedKotlinTransform() {
        val wave = FloatArray(16000 * 3 + 37) { sin(it * 0.027).toFloat() * 0.3f }
        val filters = FloatArray(NemotronConfig.MELS * NemotronConfig.BINS) { index ->
            val bin = index % NemotronConfig.BINS
            if (bin in 2..252) (1 + bin % 7) * 0.0001f else 0f
        }
        val hann = FloatArray(NemotronConfig.WIN) { 0.5f - 0.5f * kotlin.math.cos(2.0 * Math.PI * it / 399).toFloat() }
        val mel = NemotronMel(wave, filters, hann)
        for ((first, count) in listOf(0 to 7, 96 to 8, mel.frames - 7 to 7)) {
            val native = FloatArray(count * NemotronConfig.MELS)
            val reference = FloatArray(native.size)
            mel.write(first, count, native)
            mel.writeReference(first, count, reference)
            for (i in native.indices) {
                assertEquals("frame=$first index=$i", reference[i], native[i], 0.0002f)
            }
        }
        val frameCount = minOf(300, mel.frames - 1)
        val native = FloatArray(frameCount * NemotronConfig.MELS)
        val reference = FloatArray(native.size)
        mel.write(0, frameCount, native)
        mel.writeReference(0, frameCount, reference)
        fun medianMillis(block: () -> Unit): Double {
            val durations = LongArray(5) {
                val start = System.nanoTime()
                block()
                System.nanoTime() - start
            }
            return durations.sorted()[2] / 1_000_000.0
        }
        val kotlinMs = medianMillis { mel.writeReference(0, frameCount, reference) }
        val nativeMs = medianMillis { mel.write(0, frameCount, native) }
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        File(context.filesDir, "native-mel-benchmark.json").writeText(JSONObject()
            .put("scope", "emulator microbenchmark only, not HONOR RTF")
            .put("abi", Build.SUPPORTED_ABIS[0])
            .put("frames", frameCount)
            .put("native_median_ms", nativeMs)
            .put("kotlin_median_ms", kotlinMs)
            .toString(2))
    }
}
