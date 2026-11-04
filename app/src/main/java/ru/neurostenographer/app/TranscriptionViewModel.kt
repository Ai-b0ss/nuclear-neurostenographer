package ru.neurostenographer.app

import android.app.Application
import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import android.util.Log
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
    val sourceDurationMs: Long? = null, val document: TranscriptDocument? = null,
    val c2Supported: Boolean = false, val expectedSpeakers: Int = -1)

class TranscriptionViewModel @JvmOverloads constructor(application: Application,
    private val recorderFactory: (File) -> WavRecording = ::RecordWav) : AndroidViewModel(application) {
    private val store = AsrModelStore(application)
    private val speakerStore = DiarizationModelStore(application)
    /** Platform errors are English and mean nothing to a user: keep the text only as a detail. */
    private fun userMessage(e: Exception): String {
        val text = e.message ?: return "Ошибка обработки."
        return if (text.any { it in 'А'..'я' || it == 'ё' || it == 'Ё' }) text
        else "Не удалось прочитать аудиофайл: он повреждён или имеет неподдерживаемый формат. Выберите другой файл. (Деталь: $text)"
    }
    private fun c2Available(): Boolean = BuildConfig.NEMOTRON_PROTOTYPE && (
        NemotronBackend.current(getApplication<Application>().filesDir) != null ||
        runCatching { getApplication<Application>().assets.list("")?.contains("nemotron.zip") == true }
            .getOrDefault(false))
    private val mutable = MutableStateFlow(store.current().let { installed ->
        val base = ScreenState(modelReady = installed != null,
            diarizationReady = speakerStore.current() != null, c2Supported = c2Available())
        if (installed != null) base.copy(message = "Модели установлены. Выберите или запишите аудио и нажмите «Распознать офлайн».") else base
    })
    val state = mutable.asStateFlow()
    private var operation: Job? = null
    private var recorder: WavRecording? = null
    private var recordingTimer: Job? = null
    var recording = MutableStateFlow(false)
        private set

    private var pendingExport: Pair<String, String>? = null

    fun setExpectedSpeakers(count: Int) {
        require(count == -1 || count in 2..4)
        if (mutable.value.busy || recording.value || (count != -1 && !mutable.value.diarizationReady)) return
        if (mutable.value.expectedSpeakers == count) return
        mutable.value = mutable.value.copy(expectedSpeakers = count, document = null,
            segments = emptyList(), speakerSource = "not_run", timestampSource = "input_windows",
            message = "Параметр числа говорящих изменён. Запустите распознавание заново.")
    }

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
            catch (_: OutOfMemoryError) { mutable.value = mutable.value.copy(message = "Недостаточно RAM. Попробуйте более короткую запись.") }
            catch (e: LinkageError) { mutable.value = mutable.value.copy(message = "Ошибка JNI: ${e.message}") }
            catch (e: Exception) { mutable.value = mutable.value.copy(message = userMessage(e)) }
            finally { mutable.value = mutable.value.copy(busy = false, modelReady = store.current() != null,
                diarizationReady = speakerStore.current() != null, c2Supported = c2Available()) }
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

    /** Models pushed with `adb push` into the app's own external folder (no document picker).
     * They go through the same strict, SHA-256 checked importers as the manual ZIP buttons.
     */
    private fun kitFiles(): List<Pair<String, File>> {
        // A phone may report an SD card as the primary external storage while `adb push` writes to the
        // internal one (/sdcard). Look in every external files directory of the app.
        val directories = getApplication<Application>().getExternalFilesDirs(KIT_DIRECTORY).filterNotNull()
        Log.i("KitInstall", "dirs=$directories")
        return listOf(KIT_ASR_ZIP, KIT_DIARIZATION_ZIP).mapNotNull { name ->
            directories.map { File(it, name) }.firstOrNull { it.isFile }?.let { name to it }
        }
    }

    fun installKit() = work {
        val files = kitFiles()
        if (files.isEmpty()) return@work
        val app = getApplication<Application>()
        for ((name, file) in files) {
            mutable.value = mutable.value.copy(message = "Установка из папки комплекта: $name…")
            // Unpacking needs the staged copy and, until the swap, the previous model as well.
            val needed = file.length() * 2 + 64L * 1024 * 1024
            val free = app.filesDir.usableSpace
            check(free >= needed) { "Мало места для $name: нужно около ${needed / (1024 * 1024)} МБ, свободно ${free / (1024 * 1024)} МБ." }
            try {
                withContext(Dispatchers.IO) {
                    val context = currentCoroutineContext()
                    file.inputStream().use {
                        if (name == KIT_ASR_ZIP) store.install(it) { context.ensureActive() }
                        else speakerStore.install(it) { context.ensureActive() }
                    }
                }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { throw IllegalStateException("$name: ${e.message ?: "ошибка установки"}. Файл оставлен в папке комплекта.") }
            file.delete()
            mutable.value = mutable.value.copy(modelReady = store.current() != null,
                diarizationReady = speakerStore.current() != null)
        }
        mutable.value = mutable.value.copy(message = "Комплект установлен, SHA-256 проверен. Сеть не нужна.")
    }

    init { if (kitFiles().isNotEmpty()) installKit() }

    /** Prefer verified local Nemotron C2 when this product variant contains it.
     * A C2 startup, model or worker failure falls back to the unchanged C0 implementation.
     * Ordinary (non-C2) builds remain byte-for-byte compatible in their inference choices.
     */
    fun transcribe() = work {
        val source = requireNotNull(mutable.value.source) { "Выберите WAV" }
        val expectedSpeakers = mutable.value.expectedSpeakers
        mutable.value = mutable.value.copy(segments = emptyList(), document = null,
            message = "Чтение WAV и проверка модели…")
        val (output, diarization, processing) = withContext(Dispatchers.IO) {
            val context = currentCoroutineContext()
            val app = getApplication<Application>()
            val model = requireNotNull(store.current()) { "Установите ZIP модели" }
            store.verify(model) { context.ensureActive() }
            val audio = app.contentResolver.openInputStream(source)!!.use {
                PcmWav.read(it) { context.ensureActive() }
            }
            context.ensureActive()
            var warning: String? = null
            var backendUsed: String? = null
            var speakers: DiarizationOutput? = null

            if (BuildConfig.NEMOTRON_PROTOTYPE && expectedSpeakers == -1) {
                try {
                    mutable.value = mutable.value.copy(message = "Проверка Nemotron C2 (полностью офлайн)…")
                    // The product APK carries a pinned ZIP. The research prototype can
                    // use C0 if the C2 ZIP is not bundled in its ordinary UI.
                    val c2 = NemotronBackend.current(app.filesDir)
                        ?: app.assets.open("nemotron.zip").use { NemotronBackend.install(app.filesDir, it) }
                    context.ensureActive()
                    mutable.value = mutable.value.copy(message = "Nemotron C2: диаризация всей записи…")
                    speakers = IsolatedDiarization.process(app, audio, c2, backend = NemotronBackend.C2)
                    backendUsed = NemotronBackend.C2
                } catch (e: CancellationException) { throw e }
                catch (e: Exception) {
                    warning = "Nemotron C2 недоступен: ${e.message ?: e.javaClass.simpleName}; включён резервный C0."
                }
            }
            if (speakers == null) {
                speakerStore.current()?.let { c0Model ->
                    try {
                        speakerStore.verify(c0Model) { context.ensureActive() }
                        mutable.value = mutable.value.copy(message = "Диаризация C0… Отмена завершит выделенный процесс.")
                        speakers = IsolatedDiarization.process(app, audio, c0Model,
                            backend = NemotronBackend.C0, expectedSpeakers = expectedSpeakers)
                        backendUsed = NemotronBackend.C0
                    } catch (e: CancellationException) { throw e }
                    catch (e: Exception) {
                        warning = listOfNotNull(warning, e.message ?: "Диаризация C0 недоступна")
                            .joinToString(" ")
                    }
                }
            }
            val asr = OfflineAsr.transcribe(audio, model, { context.ensureActive() }, { index, count ->
                mutable.value = mutable.value.copy(message = "Распознавание $index/$count. Отмена — после текущего фрагмента.")
            }, turns = speakers?.turns.orEmpty(), speechWindows = speakers?.windows)
            Triple(asr, speakers, backendUsed to warning)
        }
        val (backendUsed, warning) = processing
        val speakerSource = when {
            diarization == null && warning != null -> "failed_worker_unknown_speakers"
            diarization == null -> "not_run"
            backendUsed == NemotronBackend.C2 -> NemotronBackend.REVISION
            else -> DiarizationModelStore.REVISION +
                (if (expectedSpeakers > 0) "/user-speaker-count-$expectedSpeakers" else "")
        }
        val timestampSource = if (diarization == null) "input_windows" else "diarization_boundaries_and_input_windows"
        val warnings = listOfNotNull(warning, "Интервалы фрагментов, не пословное выравнивание.",
            if (expectedSpeakers > 0) "Число говорящих задано вручную: $expectedSpeakers; ошибка в числе может ухудшить разделение." else null,
            if (output.decodedWindows == 0) "Сегментация не обнаружила речевых окон; ASR не запускался." else null,
            if (output.decodedWindows > 0 && output.segments.isEmpty()) "ASR не вернул текста." else null,
            if (diarization == null) "Говорящие не определены." else null)
        val document = TranscriptDocument(output.segments.toList(), output.audioMs, TranscriptProvenance(
            "sherpa-onnx-1.12.20/gigaam-v3-ctc-int8", AsrModelStore.REVISION, timestampSource, speakerSource,
            BuildConfig.SHERPA_RUNTIME_SHA256), warnings)
        mutable.value = mutable.value.copy(segments = document.segments, document = document,
            sourceDurationMs = output.audioMs, speakerSource = speakerSource, timestampSource = timestampSource,
            message = (if (output.decodedWindows == 0) "Речевые окна не обнаружены; ASR не запускался. " else
                if (output.segments.isEmpty()) "ASR не вернул текста. " else "ASR вернул ${output.segments.size} фрагментов. ") +
                "Аудио: ${output.audioMs} мс; загрузка ${output.loadMs} мс; обработка ${output.decodeMs} мс. " +
                (if (diarization == null) "Диаризация недоступна. ASR без говорящих. " else
                    "Диаризация ${backendUsed?.uppercase()}: ${diarization.turns.filter { it.attributionEligible }.map { it.speakerId }.distinct().size} кластеров, ${diarization.processMs} мс. ") +
                (warning ?: ""))
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
            RecordingService.start(getApplication())
            try { recorder = recorderFactory(file).also { it.start() } }
            catch (e: Throwable) { file.delete(); RecordingService.stop(getApplication()); throw e }
            recording.value = true
            mutable.value = mutable.value.copy(message = "Идёт запись. Максимум — ${PcmWav.MAX_LABEL}. Предыдущий результат сохранён до успешной остановки.")
            // Foreground entry is asynchronous and can be refused (Android 14+ background-start
            // rules). Without it recording ends when the app leaves the screen: say so.
            viewModelScope.launch {
                delay(3_000)
                if (recording.value && !RecordingService.active) {
                    mutable.value = mutable.value.copy(message = "Фоновая запись недоступна: не сворачивайте приложение, иначе запись остановится и сохранится.")
                }
            }
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
            } else {
                recorder = null; recording.value = false
                RecordingService.stop(getApplication())
            }
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
            RecordingService.stop(getApplication())
        }
        super.onCleared()
    }

    companion object {
        const val KIT_DIRECTORY = "kit"
        const val KIT_ASR_ZIP = "gigaam-v3.zip"
        const val KIT_DIARIZATION_ZIP = "diarization.zip"
    }
}
