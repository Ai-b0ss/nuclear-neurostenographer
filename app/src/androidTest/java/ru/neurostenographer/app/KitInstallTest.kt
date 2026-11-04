package ru.neurostenographer.app

import android.app.Application
import android.os.SystemClock
import androidx.lifecycle.ViewModelStore
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import java.io.File

/** Installation of the model kit pushed with `adb push` into the app's own external folder.
 * Public model assets only; the same strict SHA-256 importers as the manual buttons.
 */
class KitInstallTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext

    private fun kitDirectory(): File =
        requireNotNull(context.getExternalFilesDir(TranscriptionViewModel.KIT_DIRECTORY)).also { it.mkdirs() }

    private fun startModel(owner: ViewModelStore): TranscriptionViewModel {
        lateinit var model: TranscriptionViewModel
        instrumentation.runOnMainSync {
            model = TranscriptionViewModel(context.applicationContext as Application)
            owner.put("kit", model)
        }
        return model
    }

    private fun idle(model: TranscriptionViewModel) {
        val deadline = SystemClock.elapsedRealtime() + 120_000
        while (model.state.value.busy && SystemClock.elapsedRealtime() < deadline) SystemClock.sleep(50)
        assertFalse("Kit install timeout: ${model.state.value.message}", model.state.value.busy)
    }

    @Test fun kitFolderInstallsBothModelsAndRemovesTheZips() {
        val kit = kitDirectory()
        listOf(TranscriptionViewModel.KIT_ASR_ZIP, TranscriptionViewModel.KIT_DIARIZATION_ZIP).forEach { name ->
            instrumentation.context.assets.open(name).use { input -> File(kit, name).outputStream().use { input.copyTo(it) } }
        }
        val owner = ViewModelStore()
        try {
            val model = startModel(owner)
            idle(model)
            assertTrue(model.state.value.message, model.state.value.modelReady && model.state.value.diarizationReady)
            assertTrue(model.state.value.message.contains("Комплект установлен"))
            assertFalse(File(kit, TranscriptionViewModel.KIT_ASR_ZIP).exists())
            assertFalse(File(kit, TranscriptionViewModel.KIT_DIARIZATION_ZIP).exists())
            assertNotNull(AsrModelStore(context).current())
            assertNotNull(DiarizationModelStore(context).current())
        } finally { instrumentation.runOnMainSync { owner.clear() } }
    }

    @Test fun corruptKitZipIsRejectedNamedAndKeepsThePreviousModel() {
        instrumentation.context.assets.open("gigaam-v3.zip").use { AsrModelStore(context).install(it) }
        val previous = requireNotNull(AsrModelStore(context).current())
        val bad = File(kitDirectory(), TranscriptionViewModel.KIT_ASR_ZIP)
        bad.writeBytes(ByteArray(4096) { (it * 31).toByte() })
        val owner = ViewModelStore()
        try {
            val model = startModel(owner)
            idle(model)
            assertTrue(model.state.value.message, model.state.value.message.contains(TranscriptionViewModel.KIT_ASR_ZIP))
            assertTrue("The rejected file stays for a retry", bad.exists())
            assertEquals(previous, AsrModelStore(context).current())
            assertTrue(model.state.value.modelReady)
        } finally {
            bad.delete()
            instrumentation.runOnMainSync { owner.clear() }
        }
    }
}
