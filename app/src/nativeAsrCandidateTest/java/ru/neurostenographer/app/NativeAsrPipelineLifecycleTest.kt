package ru.neurostenographer.app

import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.CancellationException
import org.junit.Assert.assertTrue
import org.junit.Test
import ru.neurostenographer.core.PcmWav

class NativeAsrPipelineLifecycleTest {
    @Test fun callbackCancellationReleasesModelAndRetrySucceeds() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val model = instrumentation.context.assets.open("gigaam-v3.zip").use {
            AsrModelStore(instrumentation.targetContext).install(it)
        }
        val audio = instrumentation.context.assets.open("nemotron-bench/acted-dmd.wav").use { PcmWav.read(it) }
        val bounds = longArrayOf(0, audio.durationMs)
        var checks = 0
        try {
            NativeAsrBridge.run(audio.samples, model.absolutePath, InferenceThreads.count(),
                bounds, { if (++checks == 3) throw CancellationException("probe cancellation") },
                { _, _ -> }, LongArray(2))
            throw AssertionError("Cancellation was not propagated")
        } catch (expected: CancellationException) {
            assertTrue(checks >= 3)
        }
        val retry = NativeAsrBridge.run(audio.samples, model.absolutePath, InferenceThreads.count(),
            bounds, {}, { _, _ -> }, LongArray(2))
        assertTrue(retry.single().isNotBlank())
    }
}
