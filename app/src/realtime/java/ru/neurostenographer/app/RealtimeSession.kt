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

data class RealtimeOptions(val silenceMs: Int = 400, val maxPhraseMs: Int = 8000, val fallback: Boolean = false,
    val adaptive: Boolean = true, val paced: Boolean = true, val invocation: String? = null,
    val consensusExperimental: Boolean = false,
    val c2Chunk72AfterThreeExperimental: Boolean = false,
    /** Live C2 on its own lower-priority thread, so VAD and ASR never wait for a diarization step. */
    val separateC2Thread: Boolean = true,
    /** Take models preloaded by the live screen instead of loading them after Start. */
    val usePreload: Boolean = true,
    /** Live C2 starts no new step while a phrase is queued or being recognized (ASR gets the fast cores). */
    val asrFirst: Boolean = true)

/** The worker owns VAD and the recognizer; live C2 runs on its own lower-priority thread (or inline when
 * [RealtimeOptions.separateC2Thread] is false). Capture only appends to the journal. Shared transcript and
 * metric state is guarded by one lock. The full-recording speaker pass runs after live C2 has stopped. */
class RealtimeSession(private val context: Context, val journal: RealtimeJournal,
    val options: RealtimeOptions = RealtimeOptions(), private val update: (String, TranscriptDocument?) -> Unit = { _, _ -> }) {
    private val cancelled = AtomicBoolean(false)
    private val queue = RealtimeQueue()
    private val transcript = RealtimeTranscript()
    private var untimedChunks = 0
    private val phrases = JSONArray()
    private val steps = JSONArray()
    private val loading = JSONArray()
    private val warnings = mutableListOf("Временные метки слов приблизительные; точное акустическое выравнивание не выполняется.")
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
    private val snapshots = TranscriptSnapshotStore(directory)
    private var lastTranscriptRevision = 0L
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
    private val lock = Any()
    @Volatile private var diarFailed = false
    @Volatile private var c2Fallback = false
    @Volatile private var stopC2 = false
    /** A phrase is queued or being decoded; with [RealtimeOptions.asrFirst] live C2 waits. */
    @Volatile private var asrPending = false
    private var preloadedModels = false
    @Volatile private var c2Thread: Thread? = null

    /** Live C2 shares the ORT session with the full pass and must stop before the session closes. */
    private fun stopLiveC2() { stopC2 = true; c2Thread?.join() }

    private fun publish(initialUnknown: Boolean = false) = synchronized(lock) { publishLocked(initialUnknown) }
    private fun publishLocked(initialUnknown: Boolean) {
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
                (if (options.consensusExperimental) "dual-pass-offline-first-preview-gap-fill-experimental"
                 else "global-offline-final-warm-postprocessed") +
                (if (options.c2Chunk72AfterThreeExperimental) "/fast-chunk72-after3-experimental" else "")
            else if (c2State == "ACTIVE") "${NemotronBackend.REVISION}/revisable-provisional" else "c2_unavailable_or_partial_unknown_speakers",
            BuildConfig.SHERPA_RUNTIME_SHA256), warnings.toList() +
                if (finalizationState == "COMPLETE") emptyList() else listOf("Метки говорящих предварительные; финальное уточнение ещё не завершено."))
        document = doc
        // All formats are first persisted under one immutable revision directory.
        // The authoritative pointer changes only after all three files are durable.
        // Root-level export files are compatibility mirrors, NOT a crash-safe group.
        val published = snapshots.publish(doc.export("json"), doc.export("txt"), doc.export("srt"),
            duration, finalizationState == "COMPLETE")
        lastTranscriptRevision = published.number
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

    private fun saveMetrics() = synchronized(lock) { saveMetricsLocked() }
    private fun saveMetricsLocked() {
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
            .put("transcript_revision", lastTranscriptRevision)
            .put("transcript_manifest", "transcript-current.json")
            .put("consensus_experimental", options.consensusExperimental)
            .put("c2_chunk72_after3_experimental", options.c2Chunk72AfterThreeExperimental)
            .put("speaker_disagreement_ms", speakerDisagreementMs).put("speaker_offline_fill_ms", speakerOfflineFillMs)
            .put("cpu_ms", Process.getElapsedCpuTime() - cpuStart).put("sampled_pss_kb", highPss)
            .put("battery_temperature_tenths_c", battery?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1))
            .put("battery_level", battery?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)).put("thermal_status", thermal())
            .put("max_lag_ms", maxLagMs).put("queue_peak", queue.peak).put("fallback", options.fallback || queue.fallback)
            .put("silence_ms", options.silenceMs).put("max_phrase_ms", options.maxPhraseMs).put("separate_c2_thread", options.separateC2Thread)
            .put("preloaded_models", preloadedModels).put("asr_first", options.asrFirst).put("disk_recovery_reads", journal.diskReads)
            .put("runtime_sha256", BuildConfig.SHERPA_RUNTIME_SHA256).put("recognizer_loads", if (nativeMs > 0) 1 else 0)
            .put("phrases", phrases).put("diarization_steps", steps).put("capture_failure", journal.failure ?: JSONObject.NULL)
            .put("loading_stages", loading).put("diarization_turns", JSONArray().also { list ->
                raw.forEach { t -> list.put(JSONObject().put("start_ms", (t.startSeconds * 1000).toLong())
                    .put("end_ms", (t.endSeconds * 1000).toLong()).put("speaker_id", "Speaker ${t.cluster + 1}")) }
            })
            .toString(2))
    }

    /** One live C2 step over the captured prefix; provisional turns get the duration part of the product
     * post-processing (no flicker under 0.24 s, same-speaker gaps under 0.4 s closed). */
    private fun c2Step(native: RealtimeNative, available: Long, eof: Boolean) {
        val config = native.diarizer.config
        val t = System.nanoTime()
        var turns: List<ClusterTurn>? = null
        var error: Exception? = null
        try {
            turns = ProvisionalTurns.smooth(native.diarizer.step(available, eof, journal::read))
            // First three C2 chunks are the standard FAST preview.
            // Reuse the existing FIFO/cache, switch only subsequent chunk size.
            // This is an explicit test-only performance experiment, never default.
            if (options.c2Chunk72AfterThreeExperimental && native.diarizer.calls == 3 &&
                native.diarizer.config == NemotronChunkConfig.FAST) native.diarizer.config = NemotronChunkConfig(72, 6, 264, 222)
        } catch (e: Exception) { error = e }
        val took = (System.nanoTime() - t) / 1_000_000
        synchronized(lock) {
            if (turns != null) {
                raw = turns
                committedMs = minOf(native.diarizer.committedSamples / 16, available / 16)
                revisedFrames = native.diarizer.revisedFrames
            } else {
                diarFailed = true; raw = emptyList(); committedMs = 0; c2State = "FAILED"
                warnings += "C2 остановлен: ${error?.javaClass?.simpleName}; говорящие неизвестны. Доступен пакетный повтор."
            }
            c2Ms += took
            steps.put(JSONObject().put("chunk", config.chunk).put("right_context", config.right)
                .put("committed_ms", committedMs).put("captured_prefix_samples", available)
                .put("context_frames", native.diarizer.contextFrames).put("process_ms", took).put("at_ms", elapsedMs())
                .put("thread", Thread.currentThread().name))
        }
        publish(); saveMetrics()
    }

    private fun run() {
        try {
            saveMetrics()
            if (cancelled.get()) { state = "CANCELLED"; publish(); saveMetrics(); return }
            val loaded = System.nanoTime()
            val stage: (String) -> Unit = { stage ->
                loading.put(JSONObject().put("stage", stage).put("elapsed_ms", elapsedMs()))
                atomic("loading.json", loading.toString(2))
                check(!cancelled.get()) { "Session cancelled during loading" }
            }
            // Models loaded while the live screen was open (RealtimePreload) are taken over; otherwise load now.
            val preloaded = if (options.usePreload) RealtimePreload.take() else null
            if (preloaded != null) stage("preloaded")
            (preloaded ?: RealtimeNative(context,
                if (options.fallback) NemotronChunkConfig.FALLBACK else NemotronChunkConfig.FAST, stage = stage)).use { native -> try {
                if (preloaded != null && options.fallback && native.hasDiarizer) native.diarizer.config = NemotronChunkConfig.FALLBACK
                nativeMs = (System.nanoTime() - loaded) / 1_000_000
                preloadedModels = preloaded != null
                state = "RUNNING"
                val segmenter = RealtimePhrases(options.silenceMs, options.maxPhraseMs)
                var cursor = 0L
                var flushed = false
                diarFailed = !native.hasDiarizer
                c2State = if (diarFailed) "UNAVAILABLE" else "ACTIVE"
                if (diarFailed) synchronized(lock) { warnings += "C2 не загрузился; ASR продолжает без говорящих. ${native.diarizationFailure}" }
                c2Thread = if (!diarFailed && options.separateC2Thread) Thread({
                    // Below the ASR/VAD worker: words first, speaker labels catch up.
                    Process.setThreadPriority(Process.THREAD_PRIORITY_BACKGROUND)
                    while (!cancelled.get() && !diarFailed && !stopC2) {
                        val eof = journal.done
                        val available = journal.samples
                        if (c2Fallback && native.diarizer.config == NemotronChunkConfig.FAST) native.diarizer.config = NemotronChunkConfig.FALLBACK
                        if (options.asrFirst && asrPending && !eof) Thread.sleep(10)
                        else if (available > 0 && native.diarizer.canStep(available, eof)) c2Step(native, available, eof)
                        else if (eof) break
                        else Thread.sleep(20)
                    }
                }, "RealtimeC2").also { it.start() } else null
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
                    if (!diarFailed && options.adaptive && queue.adapt(lag, thermal())) {
                        if (c2Thread != null) c2Fallback = true else native.diarizer.config = NemotronChunkConfig.FALLBACK
                    }
                    if (queue.size > 0) asrPending = true
                    val phrase = queue.next()
                    if (phrase != null) {
                        val t = System.nanoTime()
                        val result = native.decode(journal.read(phrase.start, (phrase.end - phrase.start).toInt()), phrase)
                        val took = (System.nanoTime() - t) / 1_000_000
                        synchronized(lock) {
                            asrMs += took
                            transcript.add(phrase, result.first, result.second)
                            if (result.second != null) untimedChunks++
                            phrases.put(JSONObject().put("start_sample", phrase.start).put("end_sample", phrase.end)
                                .put("ready_sample", phrase.readyAt).put("decode_ms", took).put("display_at_ms", elapsedMs())
                                .put("latency_from_audio_end_ms", if (options.paced) elapsedMs() - phrase.endMs else JSONObject.NULL)
                                .put("words", result.first.size).put("untimed", result.second != null))
                        }
                        asrPending = queue.size > 0
                        publish(initialUnknown = true); publish(); saveMetrics(); progressed = true
                    } else if (c2Thread == null && !diarFailed && native.diarizer.canStep(cursor, eof)) {
                        c2Step(native, cursor, eof); progressed = true
                    }
                    if (eof && queue.size == 0 && (c2Thread != null || diarFailed || !native.diarizer.canStep(cursor, true))) break
                    if (!progressed) Thread.sleep(8)
                }
                // Live C2 must finish (or stop on cancel) before the full pass reuses the same ORT session.
                c2Thread?.join()
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
                            val consensus = SpeakerConsensus.offlineFirst(raw, aligned)
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
                // Every finished session goes to the shared history (speakers may be provisional or unknown: the
                // document's provenance and warnings say so). The title is what the history list shows.
                if (state.startsWith("COMPLETE")) document?.let {
                    val stamp = java.text.SimpleDateFormat("d MMMM HH:mm", java.util.Locale("ru"))
                        .format(java.util.Date(directory.name.toLongOrNull() ?: System.currentTimeMillis()))
                    val topic = ru.neurostenographer.core.TopicTitle.suggest(it.segments)
                    val title = if (topic != null) "$topic · $stamp" else "Живая запись $stamp"
                    TranscriptHistory(context.filesDir).save(title, it)
                }
            } finally { stopLiveC2() } }
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
