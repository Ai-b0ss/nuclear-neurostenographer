package ru.neurostenographer.app

import android.app.Application
import android.net.Uri
import android.os.SystemClock
import androidx.lifecycle.ViewModelStore
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import ru.neurostenographer.core.*

/** Device tests: compile alone is NOT evidence of provider/microphone behavior. */
class AudioInputTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext

    @Test fun validImportIsSnapshotAndBadReplacementKeepsPreviousInput() {
        val source = File.createTempFile("fixture-", ".wav", context.cacheDir)
        val bad = File.createTempFile("unsupported-", ".m4a", context.cacheDir)
        val owner = ViewModelStore()
        lateinit var model: TranscriptionViewModel
        fun idle() {
            val deadline = SystemClock.elapsedRealtime() + 10_000
            while (model.state.value.busy && SystemClock.elapsedRealtime() < deadline) SystemClock.sleep(25)
            assertFalse("Import stuck", model.state.value.busy)
        }
        try {
            val data = ByteBuffer.allocate(32044).order(ByteOrder.LITTLE_ENDIAN).apply {
                put("RIFF".toByteArray()); putInt(32036); put("WAVEfmt ".toByteArray()); putInt(16)
                putShort(1); putShort(1); putInt(16000); putInt(32000); putShort(2); putShort(16)
                put("data".toByteArray()); putInt(32000)
            }.array()
            source.writeBytes(data)
            bad.writeText("unsupported codec")
            instrumentation.runOnMainSync {
                model = TranscriptionViewModel(context.applicationContext as Application)
                owner.put("test", model)
                model.select(Uri.fromFile(source))
            }
            idle()
            val accepted = model.state.value.source
            assertNotNull(accepted)
            assertNotEquals(Uri.fromFile(source), accepted)
            assertEquals(1000L, model.state.value.sourceDurationMs)
            source.writeBytes(byteArrayOf(0))
            val snapshot = File(accepted!!.path!!)
            assertEquals(1000L, snapshot.inputStream().use { PcmWav.read(it) }.durationMs)
            instrumentation.runOnMainSync { model.select(Uri.fromFile(bad)) }
            idle()
            assertEquals(accepted, model.state.value.source)
            assertEquals(1000L, model.state.value.sourceDurationMs)
            assertTrue(snapshot.isFile)
            assertNull(model.state.value.document)
            val keptFiles = File(context.cacheDir, "audio-input").listFiles()!!.toSet()
            // RIFF rejection is authoritative; never retry malformed WAV through MediaCodec.
            val duplicate = data + "data".toByteArray() + byteArrayOf(2, 0, 0, 0, 0, 0)
            ByteBuffer.wrap(duplicate).order(ByteOrder.LITTLE_ENDIAN).putInt(4, duplicate.size - 8)
            for (malformed in listOf(duplicate, data + byteArrayOf(0))) {
                bad.writeBytes(malformed)
                instrumentation.runOnMainSync { model.select(Uri.fromFile(bad)) }
                idle()
                assertEquals(accepted, model.state.value.source)
                assertEquals(1000L, model.state.value.sourceDurationMs)
                assertTrue(snapshot.isFile)
                val staged = File(context.cacheDir, "audio-input").listFiles()!!.toSet()
                assertEquals(keptFiles, staged)
            }
            instrumentation.runOnMainSync { model.clearLocalAudio() }
            idle()
            assertFalse(snapshot.exists())
            assertNull(model.state.value.source)
            assertNull(model.state.value.sourceDurationMs)
        } finally {
            instrumentation.runOnMainSync { owner.clear() }
            source.delete(); bad.delete()
        }
    }

    @Test fun exportsWriteUtf8AndTruncateExistingDestination() {
        val file = File.createTempFile("export-", ".json", context.cacheDir)
        try {
            val document = TranscriptDocument(listOf(TranscriptSegment(123, 456, null, "Привет")),
                1000, TranscriptProvenance("test", "test", "input_windows", "not_run"))
            for (format in listOf("txt", "json", "srt")) {
                file.writeText("x".repeat(10000))
                val expected = document.export(format)
                context.contentResolver.openOutputStream(Uri.fromFile(file), "wt")!!.use {
                    it.write(expected.toByteArray(Charsets.UTF_8))
                }
                assertEquals(expected, file.readText(Charsets.UTF_8))
            }
        } finally { file.delete() }
    }

    @Test fun explicitAudioCleanupRemovesOwnedFilesAndClearsSelection() {
        val owner = ViewModelStore()
        lateinit var model: TranscriptionViewModel
        val root = File(context.cacheDir, "audio-input").apply { mkdirs() }
        val staged = File(root, "encoded-test.input").apply { writeText("abandoned") }
        val recording = File(context.filesDir, "recording_123.wav").apply { writeText("test") }
        val sentinel = File(context.filesDir, "cleanup-test-unrelated.txt").apply { writeText("keep") }
        try {
            instrumentation.runOnMainSync {
                model = TranscriptionViewModel(context.applicationContext as Application)
                owner.put("cleanup", model)
                model.clearLocalAudio()
            }
            val deadline = SystemClock.elapsedRealtime() + 10000
            while (model.state.value.busy && SystemClock.elapsedRealtime() < deadline) SystemClock.sleep(25)
            assertFalse(model.state.value.busy)
            assertFalse(staged.exists()); assertFalse(recording.exists())
            assertEquals("keep", sentinel.readText())
            assertNull(model.state.value.source); assertNull(model.state.value.document)
            assertTrue(model.state.value.segments.isEmpty())
        } finally {
            instrumentation.runOnMainSync { owner.clear() }
            staged.delete(); recording.delete(); sentinel.delete()
        }
    }
}
