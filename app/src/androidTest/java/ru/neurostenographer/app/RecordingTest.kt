package ru.neurostenographer.app

import android.Manifest
import android.app.Application
import android.content.pm.PackageManager
import android.net.Uri
import android.os.ParcelFileDescriptor
import android.os.SystemClock
import androidx.lifecycle.ViewModelStore
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import ru.neurostenographer.core.*

/** Isolated emulator installation only. Never persist or upload microphone audio.
 * Fake-session state regressions and actual platform capture are separate tests.
 */
class RecordingTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext

    private fun permission() {
        val grant = instrumentation.uiAutomation.executeShellCommand(
            "pm grant ${context.packageName} android.permission.RECORD_AUDIO")
        ParcelFileDescriptor.AutoCloseInputStream(grant).use { it.readBytes() }
        assertEquals(PackageManager.PERMISSION_GRANTED, context.checkSelfPermission(Manifest.permission.RECORD_AUDIO))
    }

    private fun wav(file: File) {
        Pcm16WavWriter(file, 16000, 1).use { sink ->
            sink.append(ByteBuffer.wrap(ByteArray(6400)))
            sink.finish()
        }
    }

    @Test fun failedRecordingAndStopTimeoutPreservePreviousInput() {
        permission()
        val owner = ViewModelStore()
        val source = File.createTempFile("fixture-", ".wav", context.cacheDir)
        lateinit var model: TranscriptionViewModel
        var startFails = true
        var stopFails = false
        var stopTimeout = false
        var attempted: File? = null
        fun idle() {
            val deadline = SystemClock.elapsedRealtime() + 10_000
            while (model.state.value.busy && SystemClock.elapsedRealtime() < deadline) SystemClock.sleep(25)
            assertFalse("Operation stuck", model.state.value.busy)
        }
        try {
            wav(source)
            instrumentation.runOnMainSync {
                model = TranscriptionViewModel(context.applicationContext as Application) { output ->
                    attempted = output
                    object : WavRecording {
                        @Volatile private var active = false
                        override val isRunning get() = active
                        override fun start() {
                            check(!startFails) { "FAKE device-policy failure" }
                            active = true
                        }
                        override fun requestStop() { active = false }
                        override fun stop(): File {
                            if (stopTimeout) throw RecorderStopTimeout()
                            active = false
                            if (stopFails) { output.delete(); error("FAKE dead microphone") }
                            wav(output)
                            return output
                        }
                    }
                }
                owner.put("recording", model)
                model.select(Uri.fromFile(source))
            }
            idle()
            val previous = model.state.value.source
            assertNotNull(previous)
            val snapshot = File(previous!!.path!!)
            instrumentation.runOnMainSync { model.startRecording() }
            assertEquals(previous, model.state.value.source)
            assertFalse(model.recording.value)
            assertFalse(attempted!!.exists())
            assertTrue(snapshot.isFile)

            instrumentation.runOnMainSync {
                startFails = false; stopFails = true
                model.startRecording()
            }
            assertTrue(model.recording.value)
            assertEquals(previous, model.state.value.source)
            instrumentation.runOnMainSync { model.stopRecording() }
            idle()
            assertFalse(model.recording.value)
            assertEquals(previous, model.state.value.source)
            assertTrue(snapshot.isFile)

            instrumentation.runOnMainSync {
                stopFails = false; stopTimeout = true
                model.startRecording(); model.stopRecording()
            }
            idle()
            assertTrue(model.recording.value)
            assertEquals(previous, model.state.value.source)
            instrumentation.runOnMainSync { model.clearLocalAudio(); model.select(Uri.fromFile(source)) }
            assertFalse(model.state.value.busy)
            assertTrue(snapshot.isFile)
            assertTrue(attempted!!.isFile)
            instrumentation.runOnMainSync { stopTimeout = false; model.stopRecording() }
            idle()
            assertFalse(model.recording.value)
            assertNotEquals(previous, model.state.value.source)
            assertFalse(snapshot.exists())
            assertEquals(200L, model.state.value.sourceDurationMs)
            instrumentation.runOnMainSync { model.clearLocalAudio() }
            idle()
            assertFalse(attempted!!.exists())
        } finally {
            instrumentation.runOnMainSync { owner.clear() }
            source.delete()
        }
    }

    @Test fun platformMicrophoneProducesBoundedWavAndReleasesForNextSession() {
        permission()
        val evidence = File(context.filesDir, "recording-evidence.json")
        evidence.delete()
        val runs = org.json.JSONArray()
        repeat(2) {
            val file = File.createTempFile("recording_", ".wav", context.filesDir)
            val recorder = RecordWav(file)
            try {
                recorder.start()
                SystemClock.sleep(500)
                assertEquals(file, recorder.stop())
                assertFalse(recorder.isRunning)
                assertEquals(file, recorder.stop())
                val audio = file.inputStream().use { PcmWav.read(it) }
                assertTrue(audio.durationMs in 100..2000)
                assertEquals(16000, audio.sampleRate)
                runs.put(JSONObject().put("duration_ms", audio.durationMs).put("wav_bytes", file.length()))
            } finally {
                recorder.requestStop()
                runCatching { recorder.stop() }
                // Do not remove a file while its writer still owns it.
                if (!recorder.isRunning) file.delete()
            }
        }
        evidence.writeText(JSONObject().put("status", "PASS").put("scope", "platform_capture_only_no_asr")
            .put("sdk", android.os.Build.VERSION.SDK_INT).put("abi", android.os.Build.SUPPORTED_ABIS.first())
            .put("runs", runs).put("speech_accuracy", "NOT_SCORED").toString(2))
    }
}
