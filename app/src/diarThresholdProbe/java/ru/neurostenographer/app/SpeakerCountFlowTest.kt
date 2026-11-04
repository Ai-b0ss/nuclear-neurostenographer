package ru.neurostenographer.app

import android.app.Application
import android.net.Uri
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** End-to-end product path: user count chooses C0 and is recorded in provenance. */
class SpeakerCountFlowTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext

    @Test fun knownCountUsesLocalC0(): Unit = runBlocking {
        val assets = instrumentation.context.assets
        assets.open("gigaam-v3.zip").use { AsrModelStore(context).install(it) }
        assets.open("diarization.zip").use { DiarizationModelStore(context).install(it) }
        val app = context.applicationContext as Application
        val viewModel = TranscriptionViewModel(app)
        assertTrue(viewModel.state.value.diarizationReady)
        viewModel.setExpectedSpeakers(3)
        assertEquals(3, viewModel.state.value.expectedSpeakers)

        val source = File(context.cacheDir, "speaker-count-flow.wav")
        assets.open("asr-holdout/acted-holdout-1.wav").use { input ->
            source.outputStream().use { output -> input.copyTo(output) }
        }
        try {
            viewModel.select(Uri.fromFile(source))
            withTimeout(30_000) { viewModel.state.first { !it.busy && it.source != null } }
            viewModel.transcribe()
            val completed = withTimeout(120_000) {
                viewModel.state.first { !it.busy && it.document != null }
            }
            assertEquals(3, completed.expectedSpeakers)
            assertTrue(completed.document!!.provenance.speakerSource.endsWith("/user-speaker-count-3"))
            assertTrue(completed.document!!.segments.isNotEmpty())
            viewModel.setExpectedSpeakers(-1)
            assertEquals(-1, viewModel.state.value.expectedSpeakers)
            assertTrue(viewModel.state.value.document == null)
        } finally {
            source.delete()
            viewModel.clearLocalAudio()
        }
    }
}
