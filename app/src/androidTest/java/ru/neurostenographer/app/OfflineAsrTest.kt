package ru.neurostenographer.app

import android.Manifest
import android.content.pm.PackageManager
import android.util.Log
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import ru.neurostenographer.core.PcmWav
import ru.neurostenographer.core.TranscriptExport
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import android.app.Application
import android.net.Uri
import android.os.SystemClock
import androidx.lifecycle.ViewModelStore
import java.io.File
import org.json.JSONObject

class OfflineAsrTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()

    @Test fun importedUserAudioThroughViewModelAndDocumentExports() {
        val context = instrumentation.targetContext
        val store = AsrModelStore(context)
        instrumentation.context.assets.open("gigaam-v3.zip").use { store.install(it) }
        val source = File.createTempFile("public-fixture-", ".wav", context.cacheDir)
        val destination = File.createTempFile("transcript-", ".json", context.cacheDir)
        val owner = ViewModelStore()
        lateinit var model: TranscriptionViewModel
        fun idle() {
            val deadline = SystemClock.elapsedRealtime() + 180_000
            while (model.state.value.busy && SystemClock.elapsedRealtime() < deadline) SystemClock.sleep(25)
            assertFalse("Pipeline timeout: ${model.state.value.message}", model.state.value.busy)
        }
        try {
            instrumentation.context.assets.open("example.wav").use { input -> source.outputStream().use { input.copyTo(it) } }
            instrumentation.runOnMainSync {
                model = TranscriptionViewModel(context.applicationContext as Application)
                owner.put("real-input-test", model)
                model.select(Uri.fromFile(source))
            }
            idle()
            val selected = requireNotNull(model.state.value.source)
            assertNotEquals(Uri.fromFile(source), selected)
            source.writeBytes(byteArrayOf(0)) // processing must use the validated snapshot
            instrumentation.runOnMainSync { model.transcribe() }
            idle()
            val document = requireNotNull(model.state.value.document) { model.state.value.message }
            assertTrue(document.segments.any { it.text.contains("у лукоморья дуб зеленый") })
            assertTrue(document.segments.all { it.endMs <= document.audioMs })
            for (format in listOf("txt", "srt", "json")) {
                destination.writeText("x".repeat(100000))
                instrumentation.runOnMainSync { model.prepareExport(format) }
                if (format == "json") {
                    // Document chooser may return after input changes: keep the original export.
                    instrumentation.runOnMainSync { model.select(selected) }
                    idle()
                    assertNull(model.state.value.document)
                }
                instrumentation.runOnMainSync { model.finishExport(Uri.fromFile(destination)) }
                idle()
                val saved = destination.readText(Charsets.UTF_8)
                assertTrue(saved.contains("у лукоморья дуб зеленый"))
                assertFalse(saved.endsWith("xxxxxxxx"))
                if (format == "json") {
                    val json = JSONObject(saved)
                    assertEquals(document.audioMs, json.getLong("audio_duration_ms"))
                    assertEquals(document.segments.size, json.getJSONArray("segments").length())
                    assertEquals(document.provenance.timestampSource, json.getJSONObject("provenance").getString("timestamp_source"))
                }
                if (format == "srt") assertTrue(saved.contains(" --> "))
            }
            Log.i("AsrEvidence", "ViewModel public WAV snapshot -> real ASR -> UI document -> UTF8 TXT/SRT/JSON PASS")
        } finally {
            runCatching { model.state.value.source?.path?.let { File(it).delete() } }
            instrumentation.runOnMainSync { owner.clear() }
            source.delete(); destination.delete()
        }
    }

    @Test fun actualRussianInferenceRepeatedAndSilent() {
        val context = instrumentation.targetContext
        assertEquals(PackageManager.PERMISSION_DENIED,
            context.checkSelfPermission(Manifest.permission.INTERNET))
        val store = AsrModelStore(context)
        val model = instrumentation.context.assets.open("gigaam-v3.zip").use { store.install(it) }
        val audio = instrumentation.context.assets.open("example.wav").use { PcmWav.read(it) }
        var previous: String? = null
        repeat(2) { index ->
            store.verify(model)
            val memoryBefore = InferenceEvidence.memorySnapshot()
            val output = OfflineAsr.transcribe(audio, model)
            InferenceEvidence.asr(audio, output, index, memoryBefore)
            val text = output.segments.joinToString(" ") { it.text }
            assertTrue("Actual Russian output must be nonempty: $text", Regex("[а-яА-Я]{3,}").containsMatchIn(text))
            assertTrue("Known public fixture phrase missing: $text", text.contains("у лукоморья дуб зеленый"))
            if (previous != null) assertEquals(previous, text)
            previous = text
            assertTrue(output.segments.all { it.speakerId == null && !it.attributionReliable && it.endMs <= audio.durationMs })
            assertTrue(TranscriptExport.json(output.segments).contains("\"speaker_id\": null"))
            Log.i("AsrEvidence", "run=$index audio_ms=${output.audioMs} load_ms=${output.loadMs} decode_ms=${output.decodeMs} text=$text")
        }
        val silence = OfflineAsr.transcribe(ru.neurostenographer.core.PcmAudio(FloatArray(32000), 16000), model)
        assertTrue("Silence must not invent speech", silence.segments.isEmpty())
    }

    @Test fun maliciousOrIncompleteModelDoesNotReplaceInstalledModel() {
        val store = AsrModelStore(instrumentation.targetContext)
        val original = store.current()
        for (name in listOf("../model.int8.onnx", "model.int8.onnx")) {
            val bytes = ByteArrayOutputStream()
            ZipOutputStream(bytes).use { zip ->
                zip.putNextEntry(ZipEntry(name)); zip.write(byteArrayOf(1, 2, 3)); zip.closeEntry()
            }
            try { store.install(ByteArrayInputStream(bytes.toByteArray())); fail("Unsafe ZIP accepted") }
            catch (_: IllegalArgumentException) { }
            assertEquals(original, store.current())
        }
    }
}
