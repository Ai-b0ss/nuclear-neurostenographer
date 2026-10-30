package ru.neurostenographer.app

import android.net.Uri
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import org.json.JSONObject
import ru.neurostenographer.core.PcmWav
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.CancellationException
import kotlin.math.sqrt

/** Numeric tones verify decode/duration/cleanup; never ASR or speech quality. */
class CodecImportTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext

    @Test fun generatedCodecsBecomeValidatedPrivatePcm() {
        File(context.filesDir, "codec-import-evidence.json").delete()
        val assets = instrumentation.context.assets
        val manifest = JSONObject(assets.open("codecs/manifest.json").bufferedReader().use { it.readText() })
        val records = manifest.getJSONObject("files")
        val results = org.json.JSONArray()
        for (name in records.keys()) {
            val source = File.createTempFile("codec-", ".input", context.cacheDir)
            try {
                assets.open("codecs/$name").use { input -> source.outputStream().use { input.copyTo(it) } }
                val hash = MessageDigest.getInstance("SHA-256").digest(source.readBytes())
                    .joinToString("") { "%02x".format(it) }
                assertEquals(records.getJSONObject(name).getString("sha256"), hash)
                val snapshot = AudioImport.import(context, Uri.fromFile(source))
                try {
                    assertNotEquals(source, snapshot.file)
                    source.writeBytes(byteArrayOf(0))
                    val audio = snapshot.file.inputStream().use { PcmWav.read(it) }
                    assertEquals(16000, audio.sampleRate)
                    // MP3/AAC encoder padding can affect the decoded extent; no exact alignment claim.
                    assertTrue("$name duration=${audio.durationMs}", audio.durationMs in 1200..1450)
                    assertEquals(snapshot.durationMs, audio.durationMs)
                    assertTrue(audio.samples.all { it.isFinite() && it in -1f..1f })
                    val rms = sqrt(audio.samples.map { it.toDouble() * it }.average())
                    assertTrue("$name rms=$rms", rms in 0.04..0.3)
                    results.put(JSONObject().put("fixture", name).put("sha256", hash)
                        .put("duration_ms", audio.durationMs).put("rms", rms).put("status", "PASS"))
                } finally { snapshot.file.delete() }
            } finally { source.delete() }
        }
        assertEquals(5, results.length())
        File(context.filesDir, "codec-import-evidence.json").writeText(JSONObject()
            .put("kind", "GENERATED_NUMERIC_TONES_NOT_SPEECH").put("sdk", android.os.Build.VERSION.SDK_INT)
            .put("abis", org.json.JSONArray(android.os.Build.SUPPORTED_ABIS.toList()))
            .put("generator", manifest.getString("ffmpeg")).put("results", results).toString(2))
    }

    @Test fun rejectedAndCancelledImportLeavesNoStagedFiles() {
        val root = File(context.cacheDir, "audio-input").apply { mkdirs() }
        val before = root.list()!!.toSet()
        val source = File.createTempFile("bad-codec-", ".input", context.cacheDir)
        try {
            source.writeText("malformed compressed audio")
            assertTrue(runCatching { AudioImport.import(context, Uri.fromFile(source)) }.isFailure)
            assertEquals(before, root.list()!!.toSet())
            instrumentation.context.assets.open("codecs/tone.m4a").use { input -> source.outputStream().use { input.copyTo(it) } }
            // 1 copy iteration + EOF + post-copy + decoder loop: cancel after native setup too.
            for (at in listOf(1, 4)) {
                var calls = 0
                val error = runCatching { AudioImport.import(context, Uri.fromFile(source)) {
                    if (++calls == at) throw CancellationException("test cancellation")
                } }.exceptionOrNull()
                assertTrue(error is CancellationException)
                assertEquals(before, root.list()!!.toSet())
            }
            assertTrue(runCatching { AudioImport.import(context, Uri.parse("https://example.invalid/audio.mp3")) }.isFailure)
            assertEquals(before, root.list()!!.toSet())
            val records = JSONObject(instrumentation.context.assets.open("codecs/manifest.json")
                .bufferedReader().use { it.readText() }).getJSONObject("reject_files")
            for (name in records.keys()) {
                instrumentation.context.assets.open("codecs/$name").use { input -> source.outputStream().use { input.copyTo(it) } }
                val error = runCatching { AudioImport.import(context, Uri.fromFile(source)) }.exceptionOrNull()
                assertNotNull("Accepted negative fixture $name", error)
                val reason = when (name) {
                    "two-tracks.m4a" -> "ровно один"
                    "float-output.flac" -> "PCM16"
                    else -> "120 секунд"
                }
                assertTrue("$name: $error", error!!.message.orEmpty().contains(reason))
                assertEquals(before, root.list()!!.toSet())
            }
        } finally { source.delete() }
    }
}
