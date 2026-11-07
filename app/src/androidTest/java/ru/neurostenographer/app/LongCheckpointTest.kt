package ru.neurostenographer.app

import android.app.Application
import android.net.Uri
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Test
import org.junit.Assume.assumeTrue
import org.junit.runner.RunWith
import ru.neurostenographer.core.*
import java.io.File
import java.io.RandomAccessFile

@RunWith(AndroidJUnit4::class)
class LongCheckpointTest {
    @Test fun twentyOneMinuteFileThroughProductAndMp3Import() {
        assumeTrue(BuildConfig.ENGLISH_AUTO && BuildConfig.APPLICATION_ID.endsWith(".checkpoint"))
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val app = instrumentation.targetContext.applicationContext as Application
        val source = File(app.cacheDir, "checkpoint-long.wav")
        val seconds = 21 * 60
        val fixture = instrumentation.context.assets.open("russian.wav").use { PcmWav.read(it) }
        val samples = fixture.samples.copyOfRange(0, minOf(3 * 16000, fixture.samples.size))
        RandomAccessFile(source, "rw").use { file ->
            fun le(value: Long, n: Int) { repeat(n) { file.write((value ushr (it * 8)).toInt() and 255) } }
            val bytes = seconds * 32000L
            file.setLength(0); file.writeBytes("RIFF"); le(bytes + 36, 4); file.writeBytes("WAVEfmt ")
            le(16, 4); le(1, 2); le(1, 2); le(16000, 4); le(32000, 4); le(2, 2); le(16, 2)
            file.writeBytes("data"); le(bytes, 4); file.setLength(bytes + 44)
            for (at in listOf(0L, (seconds - 4) * 32000L)) {
                file.seek(44 + at)
                samples.forEach { le((it * 32768).toInt().coerceIn(-32768, 32767).toLong(), 2) }
            }
        }
        lateinit var viewModel: TranscriptionViewModel
        fun waitFor(label: String, timeoutMs: Long = 300_000, condition: () -> Boolean) {
            val deadline = System.nanoTime() + timeoutMs * 1_000_000
            while (!condition()) {
                check(System.nanoTime() < deadline) { "$label: ${viewModel.state.value.message}" }
                Thread.sleep(100)
            }
        }
        try {
            instrumentation.runOnMainSync { viewModel = TranscriptionViewModel(app) }
            waitFor("bundled models") { viewModel.state.value.modelReady && !viewModel.state.value.busy }
            instrumentation.runOnMainSync { viewModel.select(Uri.fromFile(source)) }
            waitFor("long import") { !viewModel.state.value.busy }
            check(viewModel.state.value.sourceDurationMs == seconds * 1000L) { viewModel.state.value.message }
            instrumentation.runOnMainSync { viewModel.transcribe() }
            waitFor("long recognition", 600_000) { !viewModel.state.value.busy }
            val document = requireNotNull(viewModel.state.value.document) { viewModel.state.value.message }
            check(document.audioMs == seconds * 1000L)
            check(document.segments.any { it.startMs < 10_000 }) { "first speech lost" }
            check(document.segments.any { it.startMs > 1_200_000 }) { "speech after old limit lost" }
            check(document.segments.all { it.speakerId == null && !it.attributionReliable })
            val json = document.export("json-contest")
            check(json.contains("\"unknown\"") && json.contains("\"transcript\""))
            File(app.filesDir, "long-checkpoint.json").writeText(json)
            // A real MP3 decoder path, not only a WAV renamed to .mp3.
            val mp3 = File(app.cacheDir, "checkpoint.mp3")
            instrumentation.context.assets.open("english.mp3").use { src -> mp3.outputStream().use { dst -> src.copyTo(dst) } }
            try {
                val imported = AudioImport.import(app, Uri.fromFile(mp3))
                check(imported.durationMs > 1000)
                check(PcmFileAudio(imported.file).durationMs == imported.durationMs)
                imported.file.delete()
            } finally { mp3.delete() }
        } finally { source.delete() }
    }
}
