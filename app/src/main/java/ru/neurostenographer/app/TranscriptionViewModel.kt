package ru.neurostenographer.app

import android.app.Application
import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.core.content.ContextCompat
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import ru.neurostenographer.core.*
import java.io.File

data class ScreenState(val source: Uri? = null, val busy: Boolean = false,
    val modelReady: Boolean = false, val message: String = "Установите локальный ZIP модели GigaAM v3 (225 МБ).",
    val segments: List<TranscriptSegment> = emptyList(), val diarizationReady: Boolean = false,
    val speakerSource: String = "not_run", val timestampSource: String = "input_windows",
    val sourceDurationMs: Long? = null, val document: TranscriptDocument? = null)

class TranscriptionViewModel @JvmOverloads constructor(application: Application,
    private val recorderFactory: (File) -> WavRecording = ::RecordWav) : AndroidViewModel(application) {
    private val store = AsrModelStore(application)
    private val speakerStore = DiarizationModelStore(application)
    private val mutable = MutableStateFlow(ScreenState(modelReady = store.current() != null,
        diarizationReady = speakerStore.current() != null))
    val state = mutable.asStateFlow()
    private var operation: Job? = null
    private var recorder: WavRecording? = null
    private var recordingTimer: Job? = null
    var recording = MutableStateFlow(false)
        private set

    private var pendingExport: Pair<String, String>? = null

    fun select(uri: Uri) = work {
        var staged: File? = null
        try {
            val snapshot = withContext(Dispatchers.IO) {
                val context = currentCoroutineContext()
                AudioImport.import(getApplication(), uri) { context.ensureActive() }.also { staged = it.file }
            }
            discardSnapshot(mutable.value.source)
            mutable.value = mutable.value.copy(source = Uri.fromFile(snapshot.file), sourceDurationMs = snapshot.durationMs,
                segments = emptyList(), document = null, speakerSource = "not_run", timestampSource = "input_windows",
                message = "Аудио проверено: ${snapshot.durationMs} мс. Нажмите «Распознать офлайн».")
            staged = null
        } finally { staged?.delete() }
    }

    private fun discardSnapshot(uri: Uri?) {
        if (uri?.scheme != "file") return
        val file = File(uri.path ?: return)
        if (file.parentFile == File(getApplication<Application>().cacheDir, "audio-input")) file.delete()
    }

    private fun work(whileRecording: Boolean = false, block: suspend () -> Unit) {
        if (mutable.value.busy || (recording.value && !whileRecording)) return
        mutable.value = mutable.value.copy(busy = true)
        operation = viewModelScope.launch {
            try { block() }
            catch (_: CancellationException) { mutable.value = mutable.value.copy(message = "Операция отменена.") }
            catch (_: OutOfMemoryError) { mutable.value = mutable.value.copy(message = "Недостаточно RAM. Попробуйте более короткий WAV.") }
            catch (e: LinkageError) { mutable.value = mutable.value.copy(message = "Ошибка JNI: ${e.message}") }
            catch (e: Exception) { mutable.value = mutable.value.copy(message = e.message ?: "Ошибка обработки") }
            finally { mutable.value = mutable.value.copy(busy = false, modelReady = store.current() != null,
                diarizationReady = speakerStore.current() != null) }
        }
    }

    fun install(uri: Uri) = work {
        mutable.value = mutable.value.copy(message = "Проверка и установка модели…")
        withContext(Dispatchers.IO) {
            val context = currentCoroutineContext()
            getApplication<Application>().contentResolver.openInputStream(uri)!!.use {
                store.install(it) { context.ensureActive() }
            }
        }
        mutable.value = mutable.value.copy(modelReady = true, message = "GigaAM v3 установлен; SHA-256 проверен.")
    }

    fun installDiarization(uri: Uri) = work {
        mutable.value = mutable.value.copy(message = "Проверка моделей диаризации…")
        withContext(Dispatchers.IO) {
            val context = currentCoroutineContext()
            requireNotNull(getApplication<Application>().contentResolver.openInputStream(uri)).use {
                speakerStore.install(it) { context.ensureActive() }
            }
        }
        mutable.value = mutable.value.copy(diarizationReady = true,
            message = "Pyannote + ERes2Net установлены; SHA-256 проверен. Кластеризация экспериментальная.")
    }

    fun transcribe() = work {
        val source = requireNotNull(mutable.value.source) { "Выберите WAV" }
        mutable.value = mutable.value.copy(segments = emptyList(), document = null, message = "Чтение WAV и проверка модели…")
        val (output, diarization, warning) = withContext(Dispatchers.IO) {
            val context = currentCoroutineContext()
            val model = requireNotNull(store.current()) { "Установите ZIP модели" }
            store.verify(model) { context.ensureActive() }
            val audio = getApplication<Application>().contentResolver.openInputStream(source)!!.use {
                PcmWav.read(it) { context.ensureActive() }
            }
            context.ensureActive()
            var warning: String? = null
            val speakers = speakerStore.current()?.let { speakerModel ->
                try {
                    speakerStore.verify(speakerModel) { context.ensureActive() }
                    mutable.value = mutable.value.copy(message = "Диаризация всей записи… Отмена завершит выделенный процесс.")
                    IsolatedDiarization.process(getApplication(), audio, speakerModel)
                } catch (e: CancellationException) { throw e }
                catch (e: Exception) { warning = e.message ?: "Диаризация недоступна"; null }
            }
            val asr = OfflineAsr.transcribe(audio, model, { context.ensureActive() }, { index, count ->
                mutable.value = mutable.value.copy(message = "Распознавание $index/$count. Отмена — после текущего фрагмента.")
            }, turns = speakers?.turns.orEmpty(), speechWindows = speakers?.windows)
            Triple(asr, speakers, warning)
        }
        val speakerSource = if (warning != null) "failed_worker_unknown_speakers" else
            if (diarization == null) "not_run" else DiarizationModelStore.REVISION
        val timestampSource = if (diarization == null) "input_windows" else "diarization_boundaries_and_input_windows"
        val warnings = listOfNotNull(warning, "Интервалы фрагментов, не пословное выравнивание.",
            if (output.decodedWindows == 0) "Сегментация не обнаружила речевых окон; ASR не запускался." else null,
            if (output.decodedWindows > 0 && output.segments.isEmpty()) "ASR не вернул текста." else null,
            if (diarization == null) "Говорящие не определены." else null)
        val document = TranscriptDocument(output.segments.toList(), output.audioMs, TranscriptProvenance(
            "sherpa-onnx-1.12.20/gigaam-v3-ctc-int8", AsrModelStore.REVISION, timestampSource, speakerSource), warnings)
        mutable.value = mutable.value.copy(segments = document.segments, document = document,
            sourceDurationMs = output.audioMs, speakerSource = speakerSource, timestampSource = timestampSource,
            message = (if (output.decodedWindows == 0) "Речевые окна не обнаружены; ASR не запускался. " else
                if (output.segments.isEmpty()) "ASR не вернул текста. " else "ASR вернул ${output.segments.size} фрагментов. ") +
                "Аудио: ${output.audioMs} мс; загрузка ${output.loadMs} мс; обработка ${output.decodeMs} мс. " +
                if (warning != null) "Диаризация не выполнена: $warning. ASR без говорящих." else
                if (diarization == null) "Без диаризации: установите diarization.zip." else
                    "Диаризация: ${diarization.turns.filter { it.attributionEligible }.map { it.speakerId }.distinct().size} кластеров, ${diarization.processMs} мс; неопределённость и перекрытия сохраняются.")
    }

    fun prepareExport(format: String) {
        val document = requireNotNull(mutable.value.document) { "Нет распознанной стенограммы" }
        pendingExport = format to document.export(format)
    }

    fun finishExport(uri: Uri?) {
        val request = pendingExport
        pendingExport = null
        if (uri == null || request == null) return
        work {
            withContext(Dispatchers.IO) {
                requireNotNull(getApplication<Application>().contentResolver.openOutputStream(uri, "wt")).use {
                    it.write(request.second.toByteArray(Charsets.UTF_8))
                }
            }
            mutable.value = mutable.value.copy(message = "Экспорт ${request.first} сохранён. Время — интервалы фрагментов, не слов.")
        }
    }

    fun startRecording() {
        if (mutable.value.busy || recording.value) return
        if (ContextCompat.checkSelfPermission(getApplication(), Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED) {
            mutable.value = mutable.value.copy(message = "Разрешение микрофона не предоставлено.")
            return
        }
        try {
            val file = File.createTempFile("recording_", ".wav", getApplication<Application>().filesDir)
            try { recorder = recorderFactory(file).also { it.start() } }
            catch (e: Throwable) { file.delete(); throw e }
            recording.value = true
            mutable.value = mutable.value.copy(message = "Идёт запись. Максимум — 120 секунд. Предыдущий результат сохранён до успешной остановки.")
            recordingTimer = viewModelScope.launch {
                yield() // Let startRecording finish publishing the observer job.
                val deadline = System.nanoTime() + PcmWav.MAX_SECONDS * 1_000_000_000L
                while (recorder?.isRunning == true && System.nanoTime() < deadline) delay(100)
                if (recording.value) stopRecording()
            }
        } catch (e: Exception) {
            recorder = null
            mutable.value = mutable.value.copy(message = e.message ?: "Ошибка микрофона")
        }
    }

    fun stopRecording(): Unit = work(whileRecording = true) {
        recordingTimer?.cancel()
        val active = requireNotNull(recorder) { "Нет активной записи" }
        try {
            val file = withContext(NonCancellable + Dispatchers.IO) { active.stop() }
            discardSnapshot(mutable.value.source)
            mutable.value = mutable.value.copy(source = Uri.fromFile(file),
                sourceDurationMs = (file.length() - 44) * 1000 / 32000, segments = emptyList(), document = null,
                speakerSource = "not_run", timestampSource = "input_windows",
                message = "WAV сохранён. Можно распознать.")
        } finally {
            // A timeout does not prove capture stopped. Keep ownership and block
            // imports/cleanup until a retry or the observer has joined the worker.
            if (active.isRunning) {
                recordingTimer = viewModelScope.launch {
                    yield() // work must clear busy before an already-finished retry.
                    while (active.isRunning) delay(100)
                    if (recording.value && recorder === active) stopRecording()
                }
            } else { recorder = null; recording.value = false }
        }
    }

    fun cancel() { operation?.cancel() }

    /** Explicit user action: delete only app-generated local audio, including abandoned imports.
     * Exported documents belong to their chosen provider and cannot be erased here.
     */
    fun clearLocalAudio() = work {
        pendingExport = null
        mutable.value = mutable.value.copy(source = null, sourceDurationMs = null, segments = emptyList(),
            document = null, speakerSource = "not_run", timestampSource = "input_windows")
        withContext(Dispatchers.IO) {
            val app = getApplication<Application>()
            val owned = listOf(
                File(app.cacheDir, "audio-input") to Regex("(input-|encoded-|decoded-).+\\.(wav|input)"),
                File(app.cacheDir, "diarization-input") to Regex("audio-.+\\.pcm"),
                app.filesDir to Regex("recording_[0-9]+\\.wav")
            )
            var failed = 0
            for ((root, pattern) in owned) {
                for (file in root.listFiles().orEmpty()) {
                    if (file.isFile && pattern.matches(file.name) && !file.delete()) failed++
                }
            }
            check(failed == 0) { "Не удалось удалить $failed локальных аудиофайлов. Повторите очистку." }
        }
        mutable.value = mutable.value.copy(
            message = "Локальные аудиокопии и результат очищены. Экспортированные документы удаляются отдельно.")
    }

    override fun onCleared() {
        // Cleanup outlives cancelled viewModelScope. Only the owned recorder is stopped.
        recorder?.let { r ->
            r.requestStop()
            Thread { runCatching { r.stop() } }.start()
        }
        super.onCleared()
    }
}
