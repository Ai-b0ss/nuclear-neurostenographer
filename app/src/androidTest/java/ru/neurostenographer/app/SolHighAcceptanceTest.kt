package ru.neurostenographer.app

import android.Manifest
import android.app.Application
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Debug
import android.os.SystemClock
import androidx.lifecycle.ViewModelStore
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Before
import org.junit.Test
import ru.neurostenographer.core.*
import java.io.ByteArrayInputStream
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread

/** Explicit physical-phone fixture suite, NEVER run against a user's installed contest package.
 * No microphone permission grant, capture, settings change, audio cleanup or unrelated files.
 * A fixture pipeline PASS is not a UI, acoustic recording, natural accuracy or gold DER PASS.
 */
class SolHighAcceptanceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private fun onMain(action: () -> Unit) = instrumentation.runOnMainSync(action)

    @Before fun isolatedPackageOnly() {
        // Skipped (not failed) in any other package, e.g. the generic emulator suite; never runs against it.
        assumeTrue("Physical .solhigh acceptance only", context.packageName == "ru.neurostenographer.app.solhigh")
        check(BuildConfig.ASR_A3 && BuildConfig.NEMOTRON_PROTOTYPE)
    }

    private fun idle(model: TranscriptionViewModel, limitMs: Long = 180_000) {
        val end = SystemClock.elapsedRealtime() + limitMs
        while (model.state.value.busy && SystemClock.elapsedRealtime() < end) SystemClock.sleep(50)
        assertFalse("Operation timed out: ${model.state.value.message}", model.state.value.busy)
    }

    @Test fun fixturePipelineAndExports() {
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val root = File(context.filesDir, "sol-high-evidence").apply { mkdirs() }
        val evidence = JSONObject().put("scope", "physical_phone_fixture_pipeline_no_ui_no_microphone")
            .put("sdk", android.os.Build.VERSION.SDK_INT).put("abi", android.os.Build.SUPPORTED_ABIS[0])
            .put("human_accuracy", "NOT_SCORED").put("cases", JSONArray())
        val cases = evidence.getJSONArray("cases")
        val speakerCountFailures = mutableListOf<String>()
        for ((name, expected) in listOf("aba.wav" to 2, "syn3-clean.wav" to 3, "syn4-noise.wav" to 4,
                "silence.wav" to 0, "acted-dev.wav" to 2)) {
            val owner = ViewModelStore()
            lateinit var model: TranscriptionViewModel
            val source = File(context.cacheDir, "sol-high-$name")
            instrumentation.context.assets.open("sol-high/$name").use { input -> source.outputStream().use { input.copyTo(it) } }
            val digest = MessageDigest.getInstance("SHA-256").digest(source.readBytes()).joinToString("") { "%02x".format(it) }
            val running = AtomicBoolean(true)
            var peakPss = 0
            val sampler = thread {
                while (running.get()) {
                    peakPss = maxOf(peakPss, Debug.MemoryInfo().also(Debug::getMemoryInfo).totalPss)
                    Thread.sleep(250)
                }
            }
            try {
                onMain { model = TranscriptionViewModel(context.applicationContext as Application); owner.put("sol", model) }
                idle(model)
                assertTrue(model.state.value.modelReady)
                assertTrue(model.state.value.c2Supported)
                onMain { model.select(Uri.fromFile(source)) }
                idle(model)
                assertNotNull(model.state.value.source)
                val started = SystemClock.elapsedRealtime()
                onMain { model.transcribe() }
                idle(model)
                val elapsed = SystemClock.elapsedRealtime() - started
                val document = requireNotNull(model.state.value.document) { model.state.value.message }
                assertEquals(NemotronBackend.REVISION, document.provenance.speakerSource)
                assertTrue(document.segments.all { it.startMs >= 0 && it.endMs > it.startMs && it.endMs <= document.audioMs })
                if (expected > 0) assertTrue("Expected nonempty Russian fixture output", document.segments.isNotEmpty())
                else assertTrue("Silence must not invent speech", document.segments.isEmpty())
                val speakers = document.segments.mapNotNull { it.speakerId }.distinct().size
                for (format in listOf("txt", "json", "srt")) {
                    val destination = File(root, "${name.removeSuffix(".wav")}.$format")
                    destination.writeText("x".repeat(100_000))
                    onMain { model.prepareExport(format); model.finishExport(Uri.fromFile(destination)) }
                    idle(model)
                    assertEquals(document.export(format), destination.readText(Charsets.UTF_8))
                }
                val row = JSONObject().put("fixture", name).put("input_sha256", digest)
                    .put("audio_ms", document.audioMs).put("wall_ms", elapsed)
                    .put("expected_fixture_speakers", expected).put("observed_speakers", speakers)
                    .put("speaker_count_gate", if (speakers == expected) "PASS" else "FAIL")
                    .put("segments", document.segments.size).put("main_process_peak_pss_kib", peakPss)
                    .put("speaker_source", document.provenance.speakerSource).put("details", model.state.value.details)
                    .put("timestamp_source", document.provenance.timestampSource)
                cases.put(row)
                if (speakers != expected) speakerCountFailures += "$name: expected $expected, observed $speakers"
                File(root, "fixture-results.json").writeText(evidence.toString(2))
            } finally {
                running.set(false); sampler.join()
                onMain { owner.clear() }
                source.delete() // only this suite's input fixture; history and exports retained
            }
        }
        assertTrue("Speaker-count mismatches: ${speakerCountFailures.joinToString("; ")}",
            speakerCountFailures.isEmpty())
    }

    @Test fun deniedMicAndMalformedInputsPreserveSelectedFixture() {
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.RECORD_AUDIO))
        val source = File(context.cacheDir, "sol-high-valid.wav")
        val bad = File(context.cacheDir, "sol-high-invalid.wav")
        instrumentation.context.assets.open("sol-high/silence.wav").use { input -> source.outputStream().use { input.copyTo(it) } }
        val owner = ViewModelStore()
        lateinit var model: TranscriptionViewModel
        try {
            onMain { model = TranscriptionViewModel(context.applicationContext as Application); owner.put("negative", model) }
            idle(model)
            onMain { model.select(Uri.fromFile(source)) }; idle(model)
            val selected = requireNotNull(model.state.value.source)
            onMain { model.startRecording() }
            assertFalse(model.recording.value)
            assertTrue(model.state.value.message.contains("Разрешение микрофона"))
            assertEquals(selected, model.state.value.source)
            for (bytes in listOf(byteArrayOf(), "RIFF\u0000\u0000\u0000\u0000WAVE".toByteArray(), "not a WAV".toByteArray())) {
                bad.writeBytes(bytes)
                onMain { model.select(Uri.fromFile(bad)) }; idle(model)
                assertEquals(selected, model.state.value.source)
                assertTrue(File(selected.path!!).isFile)
            }
            // A crafted over-duration header is rejected without allocating a 1-hour recording.
            val bytes = source.readBytes().copyOf(44)
            java.nio.ByteBuffer.wrap(bytes).order(java.nio.ByteOrder.LITTLE_ENDIAN).apply {
                putInt(4, 3600 * 32000 + 36); putInt(40, 3600 * 32000)
            }
            try { PcmWav.read(ByteArrayInputStream(bytes)); fail("Oversize WAV accepted") }
            catch (_: IllegalArgumentException) { }
            catch (_: java.io.EOFException) { }
        } finally {
            onMain { owner.clear() }; source.delete(); bad.delete()
        }
    }

    @Test fun failedC2ReplacementKeepsVerifiedModel() {
        val store = ViewModelStore()
        lateinit var model: TranscriptionViewModel
        try {
            onMain { model = TranscriptionViewModel(context.applicationContext as Application); store.put("c2-install", model) }
            idle(model)
            val before = requireNotNull(NemotronBackend.current(context.filesDir))
            val modelFile = File(before, "model.int8.ir9.onnx")
            val digest = MessageDigest.getInstance("SHA-256").digest(modelFile.readBytes())
            for (bad in listOf(byteArrayOf(), "bad archive".toByteArray())) {
                try { NemotronBackend.install(context.filesDir, ByteArrayInputStream(bad)); fail("Invalid C2 ZIP accepted") }
                catch (_: Exception) { }
                assertEquals(before, NemotronBackend.current(context.filesDir))
                assertArrayEquals(digest, MessageDigest.getInstance("SHA-256").digest(modelFile.readBytes()))
            }
            val replacement = context.assets.open("nemotron.zip").use { NemotronBackend.install(context.filesDir, it) }
            assertNotEquals(before, replacement)
            // In-flight :diarization workers may still need the old path.
            assertTrue(before.exists())
            assertArrayEquals(digest, MessageDigest.getInstance("SHA-256").digest(modelFile.readBytes()))
            assertEquals(replacement.canonicalFile, NemotronBackend.current(context.filesDir)!!.canonicalFile)
            assertArrayEquals(digest, MessageDigest.getInstance("SHA-256").digest(File(replacement, modelFile.name).readBytes()))
        } finally { onMain { store.clear() } }
    }
}
