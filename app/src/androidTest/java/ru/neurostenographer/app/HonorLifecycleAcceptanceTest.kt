package ru.neurostenographer.app

import android.app.Application
import android.os.Process
import androidx.lifecycle.ViewModelStore
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.*
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import ru.neurostenographer.core.*
import java.io.File
import java.security.MessageDigest

/** Device-only QA. Never opens the contest package. Captured audio remains private. */
class HonorLifecycleAcceptanceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext

    @Before fun isolatedPackageOnly() {
        check(context.packageName == "ru.neurostenographer.app.solhigh")
        check(BuildConfig.ASR_A3 && BuildConfig.NEMOTRON_PROTOTYPE)
    }

    private fun hash(file: File): ByteArray = MessageDigest.getInstance("SHA-256").let { digest ->
        file.inputStream().use { input ->
            val buffer = ByteArray(65536)
            while (true) { val n = input.read(buffer); if (n < 0) break; digest.update(buffer, 0, n) }
        }
        digest.digest()
    }

    private suspend fun installed(): File {
        val owner = ViewModelStore()
        lateinit var model: TranscriptionViewModel
        try {
            instrumentation.runOnMainSync {
                model = TranscriptionViewModel(context.applicationContext as Application)
                owner.put("lifecycle", model)
            }
            withTimeout(180_000) { while (model.state.value.busy) delay(50) }
            assertTrue(model.state.value.modelReady)
            return requireNotNull(NemotronBackend.current(context.filesDir))
        } finally { instrumentation.runOnMainSync { owner.clear() } }
    }

    private fun evidence(name: String, row: JSONObject) {
        File(context.filesDir, "sol-high-evidence").apply { mkdirs() }
            .resolve(name).writeText(row.put("device_scope", "physical_ARM64_QA").toString(2))
    }

    @Test fun replacingC2DuringActiveWorkerRetainsItsModelAndCompletes(): Unit = runBlocking {
        val before = installed()
        val weights = File(before, "model.int8.ir9.onnx")
        val digest = hash(weights)
        val fixture = instrumentation.context.assets.open("sol-high/aba.wav").use { PcmWav.read(it) }
        // Long enough to observe replacement while the original worker is still running.
        val audio = PcmAudio(FloatArray(120 * 16000) { fixture.samples[it % fixture.samples.size] }, 16000)
        val started = CompletableDeferred<Int>()
        val pending = async(Dispatchers.Default) {
            IsolatedDiarization.process(context, audio, before, backend = NemotronBackend.C2,
                onWorkerStarted = { started.complete(it) })
        }
        try {
            val pid = withTimeout(15_000) { started.await() }
            assertNotEquals(Process.myPid(), pid)
            delay(1000)
            assertTrue("Worker completed before replacement began", pending.isActive)
            val replacement = withContext(Dispatchers.IO) {
                context.assets.open("nemotron.zip").use { NemotronBackend.install(context.filesDir, it) }
            }
            val activeAtPublication = pending.isActive
            assertTrue("Need actual overlap between inference and model publication", activeAtPublication)
            assertNotEquals(before, replacement)
            assertEquals(replacement.canonicalFile, NemotronBackend.current(context.filesDir)!!.canonicalFile)
            assertTrue("Active worker model was deleted", before.isDirectory)
            assertArrayEquals(digest, hash(weights))
            val output = withTimeout(240_000) { pending.await() }
            assertTrue("Original worker did not return speech", output.turns.any { it.attributionEligible })
            assertTrue(output.turns.all { it.startMs >= 0 && it.endMs > it.startMs && it.endMs <= audio.durationMs })
            evidence("active-c2-replacement.json", JSONObject().put("status", "PASS")
                .put("worker_active_at_publication", activeAtPublication).put("old_model_hash_preserved", true)
                .put("audio_ms", audio.durationMs).put("turns", output.turns.size))
        } finally { pending.cancelAndJoin() }
    }


    @Test fun grantedMicrophoneProduces16kWavAndCanRestart() {
        // Permission was granted through this QA app's normal visible dialog.
        // Do not grant/revoke permissions or change device settings from a test.
        assertEquals(android.content.pm.PackageManager.PERMISSION_GRANTED,
            context.checkSelfPermission(android.Manifest.permission.RECORD_AUDIO))
        val root = File(context.filesDir, "sol-high-evidence").apply { mkdirs() }
        val runs = org.json.JSONArray()
        for (duration in listOf(20_000L, 2_000L)) {
            val file = File.createTempFile("mic-acceptance-", ".wav", root)
            val recorder = RecordWav(file)
            val playback = File.createTempFile("qa-public-playback-", ".wav", context.cacheDir)
            var player: android.media.MediaPlayer? = null
            try {
                if (duration == 20_000L) {
                    instrumentation.context.assets.open("sol-high/aba.wav").use { input ->
                        playback.outputStream().use { input.copyTo(it) }
                    }
                    player = android.media.MediaPlayer().apply {
                        setAudioAttributes(android.media.AudioAttributes.Builder()
                            .setUsage(android.media.AudioAttributes.USAGE_MEDIA)
                            .setContentType(android.media.AudioAttributes.CONTENT_TYPE_SPEECH).build())
                        setDataSource(playback.absolutePath)
                        prepare()
                        setVolume(1f, 1f) // This player only; never alter system stream volume.
                    }
                }
                recorder.start()
                player?.start()
                android.os.SystemClock.sleep(duration)
                assertEquals(file, recorder.stop())
                assertFalse(recorder.isRunning)
                assertEquals(file, recorder.stop())
                val audio = file.inputStream().use { PcmWav.read(it) }
                assertEquals(16000, audio.sampleRate)
                assertTrue(audio.durationMs in (duration - 1000)..(duration + 3000))
                runs.put(JSONObject().put("requested_ms", duration).put("duration_ms", audio.durationMs)
                    .put("rate_hz", audio.sampleRate).put("wav_bytes", file.length()))
                if (duration == 20_000L) {
                    val c2 = runBlocking { installed() }
                    val turns = runBlocking {
                        IsolatedDiarization.process(context, audio, c2, backend = NemotronBackend.C2)
                    }
                    val output = OfflineAsr.transcribe(audio, requireNotNull(AsrModelStore(context).current()),
                        turns = turns.turns, speechWindows = turns.windows)
                    val words = output.segments.joinToString(" ") { it.text }.lowercase()
                    val matched = listOf("билет", "поезд", "клавы", "коки", "спальне").count { it in words }
                    evidence("microphone-acoustic.json", JSONObject().put("probe_keywords_matched", matched)
                        .put("segments", output.segments.size).put("audio_ms", audio.durationMs)
                        .put("status", if (matched >= 2) "PASS" else "FAIL_ACOUSTIC_PROBE_NOT_HEARD")
                        .put("human_accuracy", "NOT_SCORED"))
                    assertTrue("Public QA playback was not recognized through the physical microphone; check acoustic setup", matched >= 2)
                }
            } finally {
                player?.release()
                playback.delete() // Only the temporary copy of the public playback fixture.
                recorder.requestStop()
                runCatching { recorder.stop() }
                // Retain only this QA test's private capture; never publish or clear user audio.
            }
        }
        evidence("microphone-platform.json", JSONObject().put("status", "PASS").put("runs", runs)
            .put("speech_accuracy", "NOT_SCORED").put("scope", "real_platform_capture_not_acoustic_accuracy"))
    }

    @Test fun c2WorkerDeathCancellationAndRecoveryAreExplicit(): Unit = runBlocking {
        val model = installed()
        val silence = PcmAudio(FloatArray(16000 * 2), 16000)
        var deathObserved = false
        try {
            IsolatedDiarization.process(context, silence, model, backend = NemotronBackend.C2,
                onWorkerStarted = { pid ->
                    assertNotEquals(Process.myPid(), pid)
                    Process.killProcess(pid) // Only this QA UID's dedicated worker.
                })
            fail("Worker death was silently accepted")
        } catch (_: DiarizationUnavailable) { deathObserved = true }
        val started = CompletableDeferred<Int>()
        val job = launch(Dispatchers.Default) {
            IsolatedDiarization.process(context, silence, model, backend = NemotronBackend.C2,
                onWorkerStarted = { started.complete(it) })
        }
        withTimeout(15_000) { started.await() }
        job.cancelAndJoin()
        assertTrue(job.isCancelled)
        val recovered = IsolatedDiarization.process(context, silence, model, backend = NemotronBackend.C2)
        assertTrue(recovered.turns.isEmpty())
        val staged = File(context.cacheDir, "diarization-input").listFiles().orEmpty()
        assertTrue("Staged worker samples remain after cleanup", staged.isEmpty())
        evidence("c2-worker-lifecycle.json", JSONObject().put("status", "PASS")
            .put("injected_worker_death", deathObserved).put("cancellation", true)
            .put("recovery_silence_empty", true).put("staged_cleanup", true))
    }
}
