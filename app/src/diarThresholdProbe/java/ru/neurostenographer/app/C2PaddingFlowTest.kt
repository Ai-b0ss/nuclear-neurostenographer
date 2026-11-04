package ru.neurostenographer.app

import android.app.Application
import android.net.Uri
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** Product ViewModel uses the measured C2 boundary padding and records provenance. */
class C2PaddingFlowTest {
    @Test fun productPathUsesPaddedC2(): Unit = runBlocking {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val assets = instrumentation.context.assets
        assets.open("gigaam-v3.zip").use { AsrModelStore(context).install(it) }
        assets.open("nemotron.zip").use { NemotronDiarization.install(context.filesDir, it) }
        val model = TranscriptionViewModel(context.applicationContext as Application)
        val source = File(context.cacheDir, "c2-padding-flow.wav")
        assets.open("nemotron-bench/aba.wav").use { input ->
            source.outputStream().use { output -> input.copyTo(output) }
        }
        try {
            model.select(Uri.fromFile(source))
            withTimeout(30_000) { model.state.first { !it.busy && it.source != null } }
            model.transcribe()
            val result = withTimeout(120_000) { model.state.first { !it.busy && it.document != null } }
            assertTrue(result.document!!.provenance.speakerSource.endsWith("/boundary-pad150/window-merge400"))
            assertTrue(result.document!!.segments.isNotEmpty())
        } finally {
            source.delete()
            model.clearLocalAudio()
        }
    }
}
