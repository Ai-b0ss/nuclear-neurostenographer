package ru.neurostenographer.app

import android.util.Log
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import ru.neurostenographer.core.*
import java.io.ByteArrayInputStream
import kotlinx.coroutines.runBlocking
import android.os.Process
import android.app.ActivityManager
import kotlinx.coroutines.*
import java.io.File

class OfflineDiarizationTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    @Test fun delayedWorkerExitWaitsButUnknownExitStillBlocks(): Unit = runBlocking {
        IsolatedDiarization.awaitPriorWorkerExit(null)
        val delayed = CompletableDeferred<Unit>()
        val delivery = launch { delay(25); delayed.complete(Unit) }
        IsolatedDiarization.awaitPriorWorkerExit(delayed, 1_000)
        delivery.join()
        val unknown = CompletableDeferred<Unit>()
        try {
            IsolatedDiarization.awaitPriorWorkerExit(unknown, 10)
            fail("Unconfirmed exit accepted")
        } catch (_: DiarizationUnavailable) { }
        assertFalse(unknown.isCompleted)
        try {
            withTimeout(10) { IsolatedDiarization.awaitPriorWorkerExit(unknown, 1_000) }
            fail("Caller cancellation ignored")
        } catch (_: TimeoutCancellationException) { }
        assertFalse(unknown.isCompleted)
    }
    @Test fun experimentalThresholdRejectsInvalidValuesBeforeNativeWork(): Unit = runBlocking {
        val context = instrumentation.targetContext
        val samples = PcmAudio(FloatArray(1600), 16000)
        val nonModel = File(context.cacheDir, "must-not-load-native")
        for (threshold in floatArrayOf(Float.NaN, Float.POSITIVE_INFINITY, -1f, 0.1f, 1.0f)) {
            try {
                IsolatedDiarization.process(context, samples, nonModel,
                    clusteringThreshold = threshold)
                fail("Invalid threshold accepted: $threshold")
            } catch (_: IllegalArgumentException) { }
        }
        assertTrue(OfflineDiarization.validThreshold(0.8f))
        assertTrue(OfflineDiarization.validThreshold(OfflineDiarization.THRESHOLD))
        assertTrue(DiarizationModelStore.REVISION.endsWith("/threshold-${OfflineDiarization.THRESHOLD}"))
    }
    @Test fun finalUnbindStopsNativeWorkerAfterSuccessAndCancellation(): Unit = runBlocking {
        val context = instrumentation.targetContext
        File(context.filesDir, "worker-lifecycle-evidence.json").delete()
        val store = DiarizationModelStore(context)
        val model = instrumentation.context.assets.open("diarization.zip").use { store.install(it) }
        val silence = PcmAudio(FloatArray(32000), 16000)
        val directory = File(context.cacheDir, "diarization-input").apply { mkdirs() }
        val before = directory.listFiles()!!.toSet()
        val manager = context.getSystemService(ActivityManager::class.java)
        suspend fun assertExited(pid: Int) {
            assertNotEquals(Process.myPid(), pid)
            withTimeout(10_000) {
                while (manager.runningAppProcesses.orEmpty().any { it.pid == pid }) delay(25)
            }
            assertEquals(before, directory.listFiles()!!.toSet())
        }
        var firstPid = -1
        assertTrue(IsolatedDiarization.process(context, silence, model) { firstPid = it }.turns.isEmpty())
        assertTrue(firstPid > 0)
        assertExited(firstPid)
        val started = CompletableDeferred<Int>()
        val pending = launch {
            val ownJob = currentCoroutineContext().job
            IsolatedDiarization.process(context, silence, model) { started.complete(it); ownJob.cancel() }
        }
        val cancelledPid = withTimeout(10_000) { started.await() }
        pending.cancelAndJoin()
        assertTrue(pending.isCancelled)
        assertExited(cancelledPid)
        var retryPid = -1
        assertTrue(IsolatedDiarization.process(context, silence, model) { retryPid = it }.turns.isEmpty())
        assertExited(retryPid)
        // Metadata only; no audio or private path in collected evidence.
        File(context.filesDir, "worker-lifecycle-evidence.json").writeText(
            """{"scope":"Android worker lifecycle","success_exit":true,"cancel_exit":true,"retry_exit":true,"staged_cleanup":true}""")
        Log.i("DiarizationEvidence", "success_cancel_retry worker_exit_and_staged_cleanup PASS")
    }
    @Test fun workerDeathLeavesCallerAliveAndCanRestart(): Unit = runBlocking {
        val context = instrumentation.targetContext
        val store = DiarizationModelStore(context)
        val model = instrumentation.context.assets.open("diarization.zip").use { store.install(it) }
        val silence = PcmAudio(FloatArray(32000), 16000)
        try {
            IsolatedDiarization.process(context, silence, model) { pid ->
                assertNotEquals("Worker must have its own process", Process.myPid(), pid)
                Process.killProcess(pid)
            }
            fail("Worker death must be explicit")
        } catch (_: DiarizationUnavailable) { }
        assertTrue(IsolatedDiarization.process(context, silence, model).turns.isEmpty())
        Log.i("DiarizationEvidence", "worker_death_and_restart PASS")
    }

    @Test fun knownMixedVoicesCannotKillCaller(): Unit = runBlocking {
        val context = instrumentation.targetContext
        val evidence = File(context.filesDir, "mixture-evidence.json")
        evidence.delete()
        val store = DiarizationModelStore(context)
        val model = instrumentation.context.assets.open("diarization.zip").use { store.install(it) }
        val audio = instrumentation.context.assets.open("four-speakers.wav").use { PcmWav.read(it) }
        val mixed = PcmAudio(FloatArray(5 * 16000) { i ->
            (audio.samples[i + 16000] + audio.samples[i + 7 * 16000]) * 0.5f
        }, 16000)
        try {
            val result = IsolatedDiarization.process(context, mixed, model)
            val segments = TranscriptFusion.attributeChunks(result.windows.map {
                RecognizedChunk(it.startMs, it.endMs, "synthetic attribution test only")
            }, result.turns)
            assertTrue(segments.filter { it.overlappingSpeech }.all { it.speakerId == null && !it.attributionReliable })
            evidence.writeText(org.json.JSONObject().put("scope", "public_known_mixture_worker_containment")
                .put("native_completed", true).put("caller_alive", true)
                .put("overlap_detected", segments.any { it.overlappingSpeech })
                .put("unknown_turns", result.turns.count { !it.attributionEligible })
                .put("accuracy_status", "NOT_SCORED").toString(2))
            Log.i("DiarizationEvidence", "known_mixture native_completed overlap_detected=${segments.any { it.overlappingSpeech }}")
        } catch (_: DiarizationUnavailable) {
            evidence.writeText("""{"scope":"public_known_mixture_worker_containment","native_completed":false,"caller_alive":true,"accuracy_status":"FAIL_OR_UNPROVEN"}""")
            Log.i("DiarizationEvidence", "known_mixture WORKER_FAILED caller_alive=true; overlap accuracy FAIL/UNPROVEN")
        }
    }
    @Test fun realEmbeddingsGlobalRecurrenceSilenceAndShortInput() {
        val store = DiarizationModelStore(instrumentation.targetContext)
        val model = instrumentation.context.assets.open("diarization.zip").use { store.install(it) }
        store.verify(model)
        val audio = instrumentation.context.assets.open("four-speakers.wav").use { PcmWav.read(it) }
        var previous: List<SpeakerTurn>? = null
        repeat(2) {
            val result = OfflineDiarization.process(audio, model)
            InferenceEvidence.diarization(audio, result, it)
            fun at(ms: Long) = result.turns.filter { ms in it.startMs until it.endMs }.single().speakerId
            assertEquals(at(2000), at(23000))
            assertNotEquals(at(2000), at(8000))
            assertTrue(result.turns.all { turn -> turn.endMs <= audio.durationMs })
            previous?.let { expected -> assertEquals(expected, result.turns) }
            previous = result.turns
            Log.i("DiarizationEvidence", "public_zh run=$it load_ms=${result.loadMs} process_ms=${result.processMs} turns=${result.turns}")
        }
        // Before promoting a Russian-dialogue threshold, protect the existing
        // independent public four-speaker A-B-A recurrence baseline.
        val candidate = OfflineDiarization.process(audio, model, clusteringThreshold = 0.8f)
        fun candidateAt(ms: Long) = candidate.turns.filter { ms in it.startMs until it.endMs }
            .single().speakerId
        assertEquals(candidateAt(2000), candidateAt(23000))
        assertNotEquals(candidateAt(2000), candidateAt(8000))
        assertTrue(candidate.turns.all { it.endMs <= audio.durationMs })
        assertTrue(OfflineDiarization.process(PcmAudio(FloatArray(32000), 16000), model).turns.isEmpty())
        val short = OfflineDiarization.process(PcmAudio(audio.samples.copyOfRange(16000, 6 * 16000), 16000), model)
        assertTrue(short.turns.isNotEmpty())
        assertTrue(short.turns.all { it.endMs <= 5000 })
        try { store.install(ByteArrayInputStream(byteArrayOf(1, 2))); fail("Invalid ZIP accepted") }
        catch (_: IllegalArgumentException) { }
        assertEquals(model, store.current())
    }

    @Test fun realRussianAsrUsesInferredBoundariesAndExports() {
        val context = instrumentation.targetContext
        val asr = AsrModelStore(context)
        val asrModel = instrumentation.context.assets.open("gigaam-v3.zip").use { asr.install(it) }
        val speakers = DiarizationModelStore(context)
        val speakerModel = instrumentation.context.assets.open("diarization.zip").use { speakers.install(it) }
        val audio = instrumentation.context.assets.open("example.wav").use { PcmWav.read(it) }
        val diarization = OfflineDiarization.process(audio, speakerModel)
        val candidate = OfflineDiarization.process(audio, speakerModel, clusteringThreshold = 0.8f)
        assertEquals("Lower threshold must not split one clean Russian voice",
            1, candidate.turns.filter { it.attributionEligible }
                .map { it.speakerId }.distinct().size)
        val result = OfflineAsr.transcribe(audio, asrModel, turns = diarization.turns, speechWindows = diarization.windows)
        assertTrue(result.segments.any { it.speakerId != null && it.attributionReliable })
        assertTrue(result.segments.any { Regex("[а-яА-Я]{3,}").containsMatchIn(it.text) })
        Log.i("DiarizationEvidence", "public_ru_single_voice " + TranscriptExport.json(result.segments))
    }
}
