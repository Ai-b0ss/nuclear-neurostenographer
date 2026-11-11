package ru.neurostenographer.app

import android.app.Application
import android.net.Uri
import android.os.SystemClock
import android.util.Log
import androidx.lifecycle.ViewModelStore
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File

/** QA-only Android instrumentation; never uploads or bundles user audio. */
class CrossWindowSpeakerBookDeviceTest {
    @Test fun longFileProducesMeasuredCrossWindowEvidence() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val target = instrumentation.targetContext
        assumeTrue("Experimental test is not part of default Android CI", BuildConfig.GLOBAL_SPEAKER_BOOK)
        val negativeControl = InstrumentationRegistry.getArguments().getString("qaMode") == "differentSources"
        val fixtureName = if (negativeControl) "speakerbook_unrelated_after_5min.wav" else "speakerbook_repeat_after_5min.wav"
        val source = File(requireNotNull(target.getExternalFilesDir("qa")), fixtureName)
        assertTrue("Push a permitted test WAV to QA app's external sandbox", source.isFile)
        val evidence = File(target.filesDir,
            if (negativeControl) "speakerbook-different-sources-evidence.json"
            else "speakerbook-device-evidence.json")
        val owner = ViewModelStore()
        lateinit var model: TranscriptionViewModel
        var stage = "setup"
        val start = SystemClock.elapsedRealtime()

        fun idle(limitMs: Long) {
            val deadline = SystemClock.elapsedRealtime() + limitMs
            while (model.state.value.busy && SystemClock.elapsedRealtime() < deadline) SystemClock.sleep(200)
            assertFalse("Timeout " + stage + ": " + model.state.value.message, model.state.value.busy)
        }
        try {
            instrumentation.runOnMainSync {
                model = TranscriptionViewModel(target.applicationContext as Application)
                owner.put("cross-window-qa", model)
            }
            assertTrue("ASR not provisioned", model.state.value.modelReady)
            stage = "select"
            instrumentation.runOnMainSync { model.select(Uri.fromFile(source)) }
            idle(90_000)
            assertNotNull("Input rejected: " + model.state.value.message, model.state.value.source)
            assertTrue("WAV must cross 5-minute boundary", (model.state.value.sourceDurationMs ?: 0L) > 330_000L)
            stage = "transcribe"
            val began = SystemClock.elapsedRealtime()
            instrumentation.runOnMainSync { model.transcribe() }
            idle(780_000)
            val elapsed = SystemClock.elapsedRealtime() - began
            val doc = requireNotNull(model.state.value.document) {
                "No transcript: " + model.state.value.message
            }
            val initial = doc.segments.filter { it.startMs < 100_000 }
            val repeated = doc.segments.filter { it.startMs >= 302_000 }
            val firstIds = initial.mapNotNull { it.speakerId }.toSet()
            val secondIds = repeated.mapNotNull { it.speakerId }.toSet()
            val shared = firstIds.intersect(secondIds)
            val warning = doc.warnings.joinToString(" ")
            val blocks = Regex("профили получены для ([0-9]+) блоков")
                .find(warning)?.groupValues?.get(1)?.toIntOrNull() ?: 0
            val record = JSONObject()
                .put("scope", if (negativeControl)
                    "different_source_clips_speakers_not_identity_annotated"
                    else "repeated_public_clip_gain_changed_not_independent_accuracy")
                .put("qa_mode", if (negativeControl) "differentSources" else "repeat")
                .put("duration_ms", doc.audioMs)
                .put("wall_ms", elapsed).put("rtf", elapsed.toDouble() / doc.audioMs)
                .put("segments", doc.segments.size)
                .put("first_segments", initial.size).put("second_segments", repeated.size)
                .put("first_speaker_ids", JSONArray(firstIds.toList()))
                .put("second_speaker_ids", JSONArray(secondIds.toList()))
                .put("shared_speaker_ids", JSONArray(shared.toList()))
                .put("profiled_blocks", blocks)
                .put("speaker_source", doc.provenance.speakerSource)
                .put("warning", warning)
                .put("first_text_preview", initial.joinToString(" ") { it.text }.take(250))
                .put("second_text_preview", repeated.joinToString(" ") { it.text }.take(250))
            evidence.writeText(record.toString(2))
            Log.i("SpeakerBookDeviceQA", record.toString())
            assertEquals("chunked_experimental_voice_embeddings", doc.provenance.speakerSource)
            assertFalse("False unknown-speaker warning on a long-file result", warning.contains("Говорящие не определены."))
            assertTrue("First block text missing", initial.isNotEmpty())
            assertTrue("Second block text missing", repeated.isNotEmpty())
            assertTrue("Both blocks need voice profiles", blocks >= 2)
            if (negativeControl) {
                assertTrue("Potential cross-window false-merge of speakers from different clips: " + shared,
                    shared.isEmpty())
            } else {
                assertTrue("Returned speaker was not linked across blocks", shared.isNotEmpty())
            }
        } catch (e: Throwable) {
            if (!evidence.exists()) evidence.writeText(JSONObject()
                .put("scope", "voice_link_test_error").put("stage", stage)
                .put("error", e.javaClass.simpleName).put("message", e.message ?: "")
                .put("elapsed_ms", SystemClock.elapsedRealtime() - start).toString(2))
            throw e
        } finally {
            instrumentation.runOnMainSync { owner.clear() }
        }
    }
}
