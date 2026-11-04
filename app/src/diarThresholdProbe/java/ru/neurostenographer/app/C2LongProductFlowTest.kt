package ru.neurostenographer.app

import android.app.Application
import android.net.Uri
import android.os.Debug
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong
import kotlin.concurrent.thread

/** Full import, C2+A0, and export path for the pinned 20-minute natural call. */
class C2LongProductFlowTest {
    @Test fun importTranscribeExportTwentyMinutes(): Unit = runBlocking {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val assets = instrumentation.context.assets
        assets.open("gigaam-v3.zip").use { AsrModelStore(context).install(it) }
        assets.open("nemotron.zip").use { NemotronDiarization.install(context.filesDir, it) }
        val source = File(context.cacheDir, "natural-long-product.wav")
        val digest = MessageDigest.getInstance("SHA-256")
        assets.open("nemotron-bench/natural-long-ru_000010.wav").use { input ->
            source.outputStream().use { output ->
                val buffer = ByteArray(1024 * 1024)
                while (true) {
                    val size = input.read(buffer)
                    if (size < 0) break
                    digest.update(buffer, 0, size)
                    output.write(buffer, 0, size)
                }
            }
        }
        val sha = digest.digest().joinToString("") { "%02x".format(it) }
        assertEquals("e9933e55693151a6f2c5d0f34188348d62053b66a70d9dad0dd25ffd3a408df5", sha)
        val model = TranscriptionViewModel(context.applicationContext as Application)
        val active = AtomicBoolean(true)
        val peakPss = AtomicLong(0)
        val sampler = thread {
            while (active.get()) {
                peakPss.accumulateAndGet(Debug.getPss()) { a, b -> maxOf(a, b) }
                Thread.sleep(250)
            }
        }
        val started = System.nanoTime()
        try {
            model.select(Uri.fromFile(source))
            withTimeout(120_000) { model.state.first { !it.busy && it.source != null } }
            val imported = (System.nanoTime() - started) / 1_000_000
            model.transcribe()
            val result = withTimeout(300_000) { model.state.first { !it.busy && it.document != null } }
            val processed = (System.nanoTime() - started) / 1_000_000
            val document = result.document!!
            assertEquals(1_200_000L, document.audioMs)
            assertTrue(document.provenance.speakerSource.endsWith("/boundary-pad150/window-merge400"))
            assertTrue(document.segments.isNotEmpty())
            val txt = document.export("txt")
            val json = document.export("json")
            assertTrue(txt.isNotBlank() && json.isNotBlank())
            val textHash = MessageDigest.getInstance("SHA-256").digest(
                document.segments.joinToString("\n") { it.text }.toByteArray(Charsets.UTF_8))
                .joinToString("") { "%02x".format(it) }
            File(context.filesDir, "c2-natural-long-product-evidence.json").writeText(
                JSONObject().put("audio_sha256", sha).put("audio_ms", document.audioMs)
                    .put("import_ms", imported).put("import_and_inference_ms", processed)
                    .put("total_with_export_ms", (System.nanoTime() - started) / 1_000_000)
                    .put("segments", document.segments.size)
                    .put("attributed_segments", document.segments.count { it.speakerId != null })
                    .put("text_sha256", textHash)
                    .put("txt_bytes", txt.toByteArray(Charsets.UTF_8).size)
                    .put("json_bytes", json.toByteArray(Charsets.UTF_8).size)
                    .put("peak_app_pss_kib", peakPss.get()).toString())
        } finally {
            active.set(false)
            sampler.join()
            source.delete()
            model.clearLocalAudio()
        }
    }
}
