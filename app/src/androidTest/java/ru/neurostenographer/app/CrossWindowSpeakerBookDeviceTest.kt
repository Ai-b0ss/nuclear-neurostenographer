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
        val mode = InstrumentationRegistry.getArguments().getString("qaMode") ?: "repeat"
        assertTrue("Unknown test mode", mode in setOf("repeat", "differentSources", "withoutModel"))
        val negativeControl = mode == "differentSources"
        val missingModel = mode == "withoutModel"
        val fixtureName = if (negativeControl) "speakerbook_unrelated_after_5min.wav" else "speakerbook_repeat_after_5min.wav"
        val qaDir = requireNotNull(target.getExternalFilesDir("qa"))
        val source = File(qaDir, fixtureName)
        assertTrue("Push a permitted test WAV to QA app's external sandbox", source.isFile)
        // Rename only our QA TitaNet model, restoring it even if the test fails.
        // This exercises the REAL worker's absent-model fail-closed path.
        val optionalModel = File(qaDir, "titanet/nemo_en_titanet_small.onnx")
        val heldModel = File(qaDir, "titanet/nemo_en_titanet_small.onnx.qa-hold")
        val evidence = File(target.filesDir, when (mode) {
            "differentSources" -> "speakerbook-different-sources-evidence.json"
            "withoutModel" -> "speakerbook-without-model-evidence.json"
            else -> "speakerbook-device-evidence.json"
        })
        val owner = ViewModelStore()
        lateinit var model: TranscriptionViewModel
        var stage = "setup"
        val start = SystemClock.elapsedRealtime()

        fun idle(limitMs: Long) {
            val deadline = SystemClock.elapsedRealtime() + limitMs
            while (model.state.value.busy && SystemClock.elapsedRealtime() < deadline) SystemClock.sleep(200)
            assertFalse("Timeout " + stage + ": " + model.state.value.message, model.state.value.busy)
        }
        var movedModel = false
        try {
            if (missingModel) {
                assertTrue("Missing QA TitaNet model must exist before test", optionalModel.isFile)
                assertFalse("Stale QA backup must not be overwritten", heldModel.exists())
                assertTrue("Could not temporarily rename QA model", optionalModel.renameTo(heldModel))
                movedModel = true
                assertFalse("QA model still available after rename", optionalModel.exists())
            }
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
                .put("scope", when (mode) {
                    "differentSources" -> "different_source_clips_speakers_not_identity_annotated"
                    "withoutModel" -> "missing_optional_model_must_keep_block_local_ids"
                    else -> "repeated_public_clip_gain_changed_not_independent_accuracy"
                })
                .put("qa_mode", mode)
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
            assertFalse("False unknown-speaker warning on a long-file result", warning.contains("Говорящие не определены."))
            assertTrue("First block text missing", initial.isNotEmpty())
            assertTrue("Second block text missing", repeated.isNotEmpty())
            if (missingModel) {
                assertEquals("No TitaNet must use local-only attribution",
                    "chunked_locally_scoped_speakers_no_global_link", doc.provenance.speakerSource)
                assertEquals("Unavailable model must not produce voice profiles", 0, blocks)
                assertTrue("Missing model must not reuse IDs across blocks", shared.isEmpty())
                assertTrue("First block must have local-scoped voice labels",
                    firstIds.isNotEmpty() && firstIds.all { it.startsWith("Block ") })
                assertTrue("Second block must have local-scoped voice labels",
                    secondIds.isNotEmpty() && secondIds.all { it.startsWith("Block ") })
            } else {
                assertEquals("chunked_titanet_small_voice_embeddings_qa", doc.provenance.speakerSource)
                assertTrue("Both blocks need voice profiles", blocks >= 2)
                if (negativeControl) {
                    assertTrue("Potential cross-window false-merge of speakers from different clips: " + shared,
                        shared.isEmpty())
                } else {
                    assertTrue("Returned speaker was not linked across blocks", shared.isNotEmpty())
                }
            }
        } catch (e: Throwable) {
            if (!evidence.exists()) evidence.writeText(JSONObject()
                .put("scope", "voice_link_test_error").put("stage", stage)
                .put("error", e.javaClass.simpleName).put("message", e.message ?: "")
                .put("elapsed_ms", SystemClock.elapsedRealtime() - start).toString(2))
            throw e
        } finally {
            // Always return the exact original QA model to its previous name.
            if (movedModel) {
                assertTrue("Failed to restore TitaNet QA model", heldModel.renameTo(optionalModel))
                assertTrue("Restored model missing", optionalModel.isFile)
            }
            instrumentation.runOnMainSync { owner.clear() }
        }
    }
}
