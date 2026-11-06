package ru.neurostenographer.app

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import android.os.Debug
import android.os.PowerManager
import android.os.Process
import org.json.JSONArray
import org.json.JSONObject
import ru.neurostenographer.core.*
import java.io.File
import java.util.concurrent.atomic.AtomicBoolean

data class RealtimeOptions(val silenceMs: Int = 500, val fallback: Boolean = false,
    val adaptive: Boolean = true, val paced: Boolean = true, val invocation: String? = null,
    val consensusExperimental: Boolean = false,
    val c2Chunk72AfterThreeExperimental: Boolean = false)

/** One worker owns VAD, recognizer, C2 and cache. Capture only appends to the journal.
 * Under pressure, ASR metadata is drained before more VAD/C2 and PCM stays on disk. */
class RealtimeSession(private val context: Context, val journal: RealtimeJournal,
    val options: RealtimeOptions = RealtimeOptions(), private val update: (String, TranscriptDocument?) -> Unit = { _, _ -> }) {
    private val cancelled = AtomicBoolean(false)
    private val queue = RealtimeQueue()
    private val transcript = RealtimeTranscript()
    private var untimedChunks = 0
    private val phrases = JSONArray()
    private val steps = JSONArray()
    private val loading = JSONArray()
    private val warnings = mutableListOf("Эксперимент realtime; метки токенов ASR, не точное акустическое выравнивание.")
    private var raw = emptyList<ClusterTurn>()
    private var committedMs = 0L
    private var nativeMs = 0L
    private var asrMs = 0L
    private var c2Ms = 0L
    private var finalizationMs = 0L
    private var speakerDisagreementMs = 0L
    private var speakerOfflineFillMs = 0L
    private var finalizationState = "PENDING"
    private var revisedFrames = 0L
    private var vadNs = 0L
    private val vadMs get() = vadNs / 1_000_000
    private var maxLagMs = 0L
    private var highPss = 0L
    private var c2State = "NOT_LOADED"
    private var lastThermalNs = 0L
    private var thermalStatus = 0
    private val cpuStart = Process.getElapsedCpuTime()
    @Volatile var state = "CREATED"
        private set
    @Volatile var failure: String? = null
        private set
    @Volatile var document: TranscriptDocument? = null
        private set
    val directory: File = requireNotNull(journal.file.parentFile)
    private val worker = Thread({ run() }, "RealtimeInference")
    fun start() { check(state == "CREATED"); state = "LOADING"; worker.start() }
    fun cancel() { cancelled.set(true) }
    fun join(timeoutMs: Long): Boolean { worker.join(timeoutMs); return !worker.isAlive }
    val isRunning get() = worker.isAlive

    private fun elapsedMs() = (System.nanoTime() - journal.startedNs) / 1_000_000
    private fun atomic(name: String, text: String) {
        val tmp = File(directory, "$name.tmp"); tmp.writeText(text)
        check(tmp.renameTo(File(directory, name))) { "Cannot persist realtime checkpoint" }
    }
    private fun publish(initialUnknown: Boolean = false) {
        val duration = journal.samples / 16
        if (duration == 0L) return
        val turns = raw.map {
            SpeakerTurn((it.startSeconds * 1000).toLong(), (it.endSeconds * 1000).toLong(), "Speaker ${it.cluster + 1}",
                (it.endSeconds - it.startSeconds) >= 0.3f)
        }
        val segments = transcript.snapshot(turns, committedMs, initialUnknown)
        val doc = TranscriptDocument(segments, duration, TranscriptProvenance(
            AsrModelSpec.ACTIVE.id, AsrModelStore.REVISION,
            if (untimedChunks == 0) "asr_token_timestamps" else "asr_token_timestamps_and_input_windows",
            if (finalizationState == "COMPLETE") "${NemotronBackend.REVISION}/" +
                (if (options.consensusExperimental) "dual-pass-preview-first-final-fill-experimental"
                 else "global-offline-final") +
                (if (options.c2Chunk72AfterThreeExperimental) "/fast-chunk72-after3-experimental" else "")
            else if (c2State == "ACTIVE") "${NemotronBackend.REVISION}/revisable-provisional" else "c2_unavailable_or_partial_unknown_speakers",
            BuildConfig.SHERPA_RUNTIME_SHA256), warnings.toList() +
                if (finalizationState == "COMPLETE") emptyList() else listOf("Метки говорящих предварительные; финальное уточнение ещё не завершено."))
        document = doc
        atomic("transcript.json", doc.export("json"))
        // Keep all three formats from the same document/checkpoint.
        atomic("transcript.txt", doc.export("txt")); atomic("transcript.srt", doc.export("srt"))
        update(state, doc)
    }
    private fun thermal(): Int {
        val now = System.nanoTime()
        if (Build.VERSION.SDK_INT >= 29 && now - lastThermalNs > 1_000_000_000L) {
            thermalStatus = (context.getSystemService(Context.POWER_SERVICE) as PowerManager).currentThermalStatus
            lastThermalNs = now
        }
        return thermalStatus
    }

    private fun saveMetrics() {
        highPss = maxOf(highPss, Debug.getPss())
        val battery = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val audioMs = journal.samples / 16
        atomic("metrics.json", JSONObject().put("state", state).put("failure", failure ?: JSONObject.NULL)
            .put("invocation", options.invocation ?: JSONObject.NULL).put("c2_state", c2State)
            .put("scope", if (options.paced) "PACED_DEVICE_STREAM" else "UNPACED_DEVICE_THROUGHPUT")
            .put("sdk", Build.VERSION.SDK_INT).put("samples", journal.samples).put("audio_ms", audioMs)
            .put("elapsed_ms", elapsedMs()).put("native_load_ms", nativeMs).put("asr_ms", asrMs).put("c2_ms", c2Ms).put("vad_ms", vadMs)
            .put("compute_rtf", if (audioMs > 0) (asrMs + c2Ms + vadMs).toDouble() / audioMs else JSONObject.NULL)
            .put("finalization_ms", finalizationMs).put("finalization_state", finalizationState).put("revised_frames", revisedFrames)
            .put("consensus_experimental", options.consensusExperimental)
            .put("c2_chunk72_after3_experimental", options.c2Chunk72AfterThreeExperimental)
            .put("speaker_disagreement_ms", speakerDisagreementMs).put("speaker_offline_fill_ms", speakerOfflineFillMs)
            .put("cpu_ms", Process.getElapsedCpuTime() - cpuStart).put("sampled_pss_kb", highPss)
            .put("battery_temperature_tenths_c", battery?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1))
            .put("battery_level", battery?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)).put("thermal_status", thermal())
            .put("max_lag_ms", maxLagMs).put("queue_peak", queue.peak).put("fallback", options.fallback || queue.fallback)
            .put("silence_ms", options.silenceMs).put("max_phrase_ms", 15000).put("disk_recovery_reads", journal.diskReads)
            .put("runtime_sha256", BuildConfig.SHERPA_RUNTIME_SHA256).put("recognizer_loads", if (nativeMs > 0) 1 else 0)
            .put("phrases", phrases).put("diarization_steps", steps).put("capture_failure", journal.failure ?: JSONObject.NULL)
            .put("loading_stages", loading).put("diarization_turns", JSONArray().also { list ->
                raw.forEach { t -> list.put(JSONObject().put("start_ms", (t.startSeconds * 1000).toLong())
                    .put("end_ms", (t.endSeconds * 1000).toLong()).put("speaker_id", "Speaker ${t.cluster + 1}")) }
            })
            .toString(2))
    }

    private fun run() {
        try {
            saveMetrics()
            if (cancelled.get()) { state = "CANCELLED"; publish(); saveMetrics(); return }
            val loaded = System.nanoTime()
            RealtimeNative(context, if (options.fallback) NemotronChunkConfig.FALLBACK else NemotronChunkConfig.FAST) { stage ->
                loading.put(JSONObject().put("stage", stage).put("elapsed_ms", elapsedMs()))
                atomic("loading.json", loading.toString(2))
                check(!cancelled.get()) { "Session cancelled during loading" }
            }.use { native ->
                nativeMs = (System.nanoTime() - loaded) / 1_000_000
                state = "RUNNING"
                val segmenter = RealtimePhrases(options.silenceMs)
                var cursor = 0L
                var flushed = false
                var diarFailed = !native.hasDiarizer
                c2State = if (diarFailed) "UNAVAILABLE" else "ACTIVE"
                if (diarFailed) warnings += "C2 не загрузился; ASR продолжает без говорящих. ${native.diarizationFailure}"
                while (!cancelled.get()) {
                    val available = journal.samples
                    val remaining = available - cursor
                    var progressed = false
                    if (remaining >= 512 || (journal.done && remaining > 0)) {
                        val count = minOf(512L, remaining).toInt()
                        val frame = journal.read(cursor, count)
                        val t = System.nanoTime()
                        val speech = native.speech(if (count == 512) frame else frame.copyOf(512))
                        vadNs += System.nanoTime() - t
                        segmenter.accept(count, speech) { start, size -> QuietCuts.phraseCut(journal.read(start, size)) }.forEach(queue::add)
                        cursor += count; progressed = true
                    }
                    val eof = journal.done && cursor == journal.samples
                    if (eof && !flushed) { segmenter.finish().forEach(queue::add); flushed = true }
                    val lag = journal.samples - cursor
                    maxLagMs = maxOf(maxLagMs, lag / 16)
                    if (!diarFailed && options.adaptive && queue.adapt(lag, thermal())) native.diarizer.config = NemotronChunkConfig.FALLBACK
                    val phrase = queue.next()
                    if (phrase != null) {
                        val t = System.nanoTime()
                        val result = native.decode(journal.read(phrase.start, (phrase.end - phrase.start).toInt()), phrase)
                        val took = (System.nanoTime() - t) / 1_000_000; asrMs += took
                        transcript.add(phrase, result.first, result.second)
                        if (result.second != null) untimedChunks++
                        phrases.put(JSONObject().put("start_sample", phrase.start).put("end_sample", phrase.end)
                            .put("ready_sample", phrase.readyAt).put("decode_ms", took).put("display_at_ms", elapsedMs())
                            .put("latency_from_audio_end_ms", if (options.paced) elapsedMs() - phrase.endMs else JSONObject.NULL)
                            .put("words", result.first.size).put("untimed", result.second != null))
                        publish(initialUnknown = true); publish(); saveMetrics(); progressed = true
                    } else if (!diarFailed && native.diarizer.canStep(cursor, eof)) {
                        val config = native.diarizer.config
                        val t = System.nanoTime()
                        try {
                            raw = native.diarizer.step(cursor, eof, journal::read)
                            committedMs = minOf(native.diarizer.committedSamples / 16, cursor / 16)
                            revisedFrames = native.diarizer.revisedFrames
                            // First three C2 chunks are the standard FAST preview.
                            // Reuse the existing FIFO/cache, switch only subsequent chunk size.
                            // This is an explicit test-only performance experiment, never default.
                            if (options.c2Chunk72AfterThreeExperimental &&
                                native.diarizer.calls == 3 &&
                                native.diarizer.config == NemotronChunkConfig.FAST) {
                                native.diarizer.config = NemotronChunkConfig(72, 6, 264, 222)
                            }
                        } catch (e: Exception) {
                            diarFailed = true; raw = emptyList(); committedMs = 0
                            c2State = "FAILED"
                            warnings += "C2 остановлен: ${e.javaClass.simpleName}; говорящие неизвестны. Доступен пакетный повтор."
                        }
                        val took = (System.nanoTime() - t) / 1_000_000; c2Ms += took
                        steps.put(JSONObject().put("chunk", config.chunk).put("right_context", config.right)
                            .put("committed_ms", committedMs).put("captured_prefix_samples", cursor)
                            .put("context_frames", native.diarizer.contextFrames).put("process_ms", took).put("at_ms", elapsedMs()))
                        publish(); saveMetrics(); progressed = true
                    }
                    if (eof && queue.size == 0 && (diarFailed || !native.diarizer.canStep(cursor, true))) break
                    if (!progressed) Thread.sleep(8)
                }
                if (!cancelled.get() && native.hasDiarizer && journal.samples > 0) {
                    state = "FINALIZING"; finalizationState = "RUNNING"; publish(); saveMetrics()
                    val began = System.nanoTime()
                    try {
                        val final = native.finalizeSpeakers(journal.samples, journal::read) {
                            check(!cancelled.get()) { "Finalization cancelled" }
                            highPss = maxOf(highPss, Debug.getPss())
                        }
                        val aligned = SpeakerIdentity.align(final, raw)
                        if (options.consensusExperimental) {
                            val consensus = SpeakerConsensus.previewFirst(raw, aligned)
                            raw = consensus.turns
                            speakerDisagreementMs = consensus.disagreementMs
                            speakerOfflineFillMs = consensus.offlineFillMs
                        } else raw = aligned
                        committedMs = journal.samples / 16
                        finalizationState = "COMPLETE"; c2State = "ACTIVE"; diarFailed = false
                    } catch (e: Exception) {
                        finalizationState = if (cancelled.get()) "CANCELLED" else "FAILED"
                        warnings += "Финальное уточнение не завершено: ${e.javaClass.simpleName}. Сохранены слова и предварительная атрибуция."
                    } finally {
                        finalizationMs = (System.nanoTime() - began) / 1_000_000
                        c2Ms += finalizationMs
                    }
                }
                state = if (cancelled.get()) "CANCELLED" else if (journal.failure != null) "CAPTURE_INTERRUPTED" else "COMPLETE"
                if (diarFailed && state == "COMPLETE") state = "COMPLETE_UNKNOWN_SPEAKERS"
                if (state == "COMPLETE" && finalizationState != "COMPLETE") state = "COMPLETE_PROVISIONAL"
                publish(); saveMetrics()
                if (state == "COMPLETE") document?.let { TranscriptHistory(context.filesDir).save("Realtime ${directory.name}", it) }
            }
        } catch (e: Throwable) {
            failure = if (cancelled.get()) null else "${e.javaClass.simpleName}: ${e.message}"
            state = if (cancelled.get()) "CANCELLED" else "FAILED"
            runCatching { saveMetrics() }; update("$state: $failure", document)
        } finally {
            queue.clear()
            // Capture owns writer close; inference never closes or deletes a live WAV.
            update(state, document)
        }
    }
}
