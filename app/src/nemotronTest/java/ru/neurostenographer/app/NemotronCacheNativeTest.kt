package ru.neurostenographer.app

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import ru.neurostenographer.core.NativeNemotronSpeakerCache
import ru.neurostenographer.core.NemotronConfig
import ru.neurostenographer.core.NemotronSpeakerCacheReference
import ru.neurostenographer.core.NemotronStep
import kotlin.math.cos
import kotlin.math.sin

@RunWith(AndroidJUnit4::class)
class NemotronCacheNativeTest {
    @Test fun nativeCacheMatchesReferenceAcrossCompression() {
        val silence = FloatArray(NemotronConfig.HIDDEN) { sin(it * 0.003).toFloat() }
        val reference = NemotronSpeakerCacheReference(silence)
        NativeNemotronSpeakerCache(silence).use { native ->
            for (chunk in listOf(340, 340, 90, 340, 25)) {
                assertEquals(reference.contextFrames(), native.contextFrames())
                val context = reference.contextFrames()
                val frames = context + chunk + NemotronConfig.RIGHT_CONTEXT
                val logits = FloatArray(frames * NemotronConfig.SUBSAMPLING * NemotronConfig.SPEAKERS) { index ->
                    (sin(index * 0.017) * 2.0 + cos(index * 0.003)).toFloat()
                }
                val embeds = FloatArray(frames * NemotronConfig.HIDDEN) { index ->
                    sin(index * 0.0023).toFloat() * 0.1f
                }
                val step = NemotronStep(logits, frames * NemotronConfig.SUBSAMPLING, embeds, frames)
                reference.update(step, chunk)
                native.update(step, chunk)
                assertEquals(reference.contextFrames(), native.contextFrames())
                val expected = reference.context()
                val actual = native.context()
                assertEquals(expected.size, actual.size)
                for (i in expected.indices) assertEquals("chunk=$chunk index=$i", expected[i], actual[i], 0.0002f)
            }
        }
    }
}
