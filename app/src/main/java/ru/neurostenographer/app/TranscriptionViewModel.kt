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
    val modelReady: Boolean = false, val message: String = "Установите локальный ZIP модели ${AsrModelSpec.ACTIVE.label} (${AsrModelSpec.ACTIVE.sizeLabel}).",
    val segments: List<TranscriptSegment> = emptyList(), val diarizationReady: Boolean = false,
    val speakerSource: String = "not_run", val timestampSource: String = "input_windows",
    val sourceDurationMs: Long? = null, val document: TranscriptDocument? = null,
    val c2Supported: Boolean = false, val sourceName: String? = null, val progress: Float? = null,
    val history: List<SavedTranscript> = emptyList(), val current: SavedTranscript? = null,
    val details: String = "", val userTerms: List<Term> = emptyList(),
    /** 0 = no recognition running, 1 = preparing, 2 = speakers, 3 = speech. Only drives the progress steps in the UI. */
    val stage: Int = 0)

class TranscriptionViewModel @JvmOverloads constructor(application: Application,
    private val recorderFactory: (File) -> WavRecording = ::RecordWav) : AndroidViewModel(application) {
    private val store = AsrModelStore(application)
    private val speakerStore = DiarizationModelStore(application)
    private val history = TranscriptHistory(application.filesDir)
    private val terms = UserTerms(application.filesDir)
    private fun bundled(name: String) = runCatching { getApplication<Application>().assets.list("")?.contains(name) == true }.getOrDefault(false)
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
            diarizationReady = speakerStore.current() != null, c2Supported = c2Available(),
            history = runCatching { history.list() }.getOrDefault(emptyList()), userTerms = terms.list())
        if (installed != null) base.copy(message = READY) else base
    })
    val state = mutable.asStateFlow()
    private var operation: Job? = null
    private var recorder: WavRecording? = null
    private var recordingTimer: Job? = null
    var recording = MutableStateFlow(false)
        private set

    private var pendingExport: Pair<String, String>? = null

    fun select(uri: Uri) = work {
        // Make the otherwise slow provider copy/RIFF validation visible immediately.
        mutable.value = mutable.value.copy(message = "Открываю аудиофайл…", progress = null)
        var staged: File? = null
        try {
            val snapshot = withContext(Dispatchers.IO) {
                val context = currentCoroutineContext()
                AudioImport.import(getApplication(), uri) { context.ensureActive() }.also { staged = it.file }
            }
            discardSnapshot(mutable.value.source)
            val name = runCatching {
                getApplication<Application>().contentResolver.query(uri, arrayOf(android.provider.OpenableColumns.DISPLAY_NAME), null, null, null)
                    ?.use { c -> if (c.moveToFirst()) c.getString(0) else null }
            }.getOrNull() ?: "Аудиофайл"
            mutable.value = mutable.value.copy(source = Uri.fromFile(snapshot.file), sourceDurationMs = snapshot.durationMs,
                sourceName = name, segments = emptyList(), document = null, current = null,
                speakerSource = "not_run", timestampSource = "input_windows",
                message = "Аудио проверено: ${clock(snapshot.durationMs)}.")
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
            catch (_: CancellationException) {
                mutable.value = mutable.value.copy(message = if (mutable.value.source != null)
                    "Расшифровка остановлена. Аудио можно расшифровать снова или удалить." else "Операция отменена.")
            }
            catch (_: OutOfMemoryError) { mutable.value = mutable.value.copy(message = "Недостаточно RAM. Попробуйте более короткую запись.") }
            catch (e: LinkageError) { mutable.value = mutable.value.copy(message = "Ошибка JNI: ${e.message}") }
            catch (e: Exception) { mutable.value = mutable.value.copy(message = userMessage(e)) }
            finally { mutable.value = mutable.value.copy(busy = false, progress = null, stage = 0, modelReady = store.current() != null,
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
        mutable.value = mutable.value.copy(modelReady = true, message = "${AsrModelSpec.ACTIVE.label} установлен; SHA-256 проверен.")
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

    /** The product APK carries A3 and C2 as pinned ZIPs: unpack and verify them once, on first start. */
    private fun prepareBundled() = work {
        val app = getApplication<Application>()
        if (store.current() == null && bundled(KIT_ASR_ZIP)) {
            mutable.value = mutable.value.copy(message = "Первый запуск: готовлю приложение к работе (около минуты, один раз)…")
            withContext(Dispatchers.IO) {
                val context = currentCoroutineContext()
                app.assets.open(KIT_ASR_ZIP).use { store.install(it) { context.ensureActive() } }
            }
        }
        if (BuildConfig.NEMOTRON_PROTOTYPE && NemotronBackend.current(app.filesDir) == null && bundled("nemotron.zip")) {
            mutable.value = mutable.value.copy(message = "Первый запуск: готовлю определение говорящих…")
            withContext(Dispatchers.IO) { app.assets.open("nemotron.zip").use { NemotronBackend.install(app.filesDir, it) } }
        }
        mutable.value = mutable.value.copy(modelReady = store.current() != null,
            message = if (store.current() != null) READY else "Модель распознавания не встроена в эту сборку.")
    }

    init { if (kitFiles().isNotEmpty()) installKit() else prepareBundled() }

    fun open(id: String) {
        val item = mutable.value.history.firstOrNull { it.id == id } ?: return
        mutable.value = mutable.value.copy(current = item, document = item.document, segments = item.document.segments)
    }

    fun closeTranscript() { mutable.value = mutable.value.copy(current = null) }
    fun refreshHistory() {
        if (mutable.value.busy || recording.value) return
        viewModelScope.launch {
            val saved = withContext(Dispatchers.IO) { history.list() }
            mutable.value = mutable.value.copy(history = saved)
        }
    }

    fun delete(id: String) = work {
        withContext(Dispatchers.IO) { history.delete(id) }
        val left = withContext(Dispatchers.IO) { history.list() }
        mutable.value = mutable.value.copy(history = left, current = mutable.value.current?.takeIf { it.id != id },
            message = "Стенограмма удалена.")
    }

    fun deleteMany(ids: Set<String>) = work {
        withContext(Dispatchers.IO) { ids.forEach { history.delete(it) } }
        val left = withContext(Dispatchers.IO) { history.list() }
        mutable.value = mutable.value.copy(history = left, current = mutable.value.current?.takeIf { it.id !in ids },
            message = if (ids.size == 1) "Стенограмма удалена." else "Удалено стенограмм: ${ids.size}.")
    }

    fun rename(id: String, title: String) = work {
        val clean = title.trim().take(120)
        if (clean.isEmpty()) return@work
        withContext(Dispatchers.IO) { history.rename(id, clean) }
        val left = withContext(Dispatchers.IO) { history.list() }
        mutable.value = mutable.value.copy(history = left, current = left.firstOrNull { it.id == id })
    }

    fun renameSpeaker(id: String, speakerId: String, name: String) = work {
        val clean = name.replace(Regex("[\r\n\t]+"), " ").trim().take(40)
        withContext(Dispatchers.IO) { history.setSpeakerName(id, speakerId, clean) }
        val left = withContext(Dispatchers.IO) { history.list() }
        mutable.value = mutable.value.copy(history = left, current = left.firstOrNull { it.id == id })
    }

    private fun currentNames() = mutable.value.current?.speakerNames.orEmpty()
    private fun currentEdits() = mutable.value.current?.termEdits.orEmpty()

    /** Spelling proposals for the open transcript that were neither accepted nor declined yet. */
    fun termSuggestions(item: SavedTranscript): List<TermEdit> {
        val done = item.termEdits.map { it.key() }.toSet() + item.dismissedTerms
        return TermDictionary.suggest(item.document.segments, BuiltinTerms.ALL + mutable.value.userTerms).filter { it.key() !in done }
    }

    fun resolveTerms(id: String, accepted: List<TermEdit>, declined: List<TermEdit>) = work {
        withContext(Dispatchers.IO) { history.setTermEdits(id, accepted, declined) }
        reloadCurrent(id)
    }

    fun revertTerms(id: String) = work {
        withContext(Dispatchers.IO) { history.setTermEdits(id, emptyList(), emptyList(), reset = true) }
        reloadCurrent(id)
    }

    fun addUserTerm(heard: String, canonical: String) = work {
        if (heard.isBlank() || canonical.isBlank()) return@work
        val all = withContext(Dispatchers.IO) { terms.add(heard, canonical) }
        mutable.value = mutable.value.copy(userTerms = all)
    }

    private suspend fun reloadCurrent(id: String) {
        val left = withContext(Dispatchers.IO) { history.list() }
        mutable.value = mutable.value.copy(history = left, current = left.firstOrNull { it.id == id })
    }

    /** TXT of the open transcript for the system share sheet (the app itself has no network access). */
    fun shareText(): String? = mutable.value.document?.export("txt", currentNames(), currentEdits())

    /** Prefer verified local Nemotron C2 when this product variant contains it.
     * A C2 startup, model or worker failure falls back to the unchanged C0 implementation.
     * Ordinary (non-C2) builds remain byte-for-byte compatible in their inference choices.
     */
    fun transcribe() = work {
        val source = requireNotNull(mutable.value.source) { "Выберите WAV" }
        mutable.value = mutable.value.copy(segments = emptyList(), document = null, current = null,
            message = "Готовлю запись…", stage = 1)
        val (output, diarization, processing) = withContext(Dispatchers.IO) {
            val context = currentCoroutineContext()
            val model = requireNotNull(store.current()) { "Установите ZIP модели" }
            store.verify(model) { context.ensureActive() }
            require(source.scheme == "file") { "Аудиофайл должен быть сохранён локально" }
            val pcm = PcmFileAudio(File(requireNotNull(source.path))) { context.ensureActive() }
            if (pcm.durationMs > PcmWav.MAX_SECONDS * 1000L) recognizeLong(pcm, model)
            else recognizeBlock(pcm.read(checkCancelled = { context.ensureActive() }), model)
        }
        val (backendUsed, warning) = processing
        val speakerSource = when {
            backendUsed == "long-file" -> "chunked_unknown_global_speakers"
            backendUsed == "digital-silence" -> "digital_silence_no_diarization"
            diarization == null && warning != null -> "failed_worker_unknown_speakers"
            diarization == null -> "not_run"
            backendUsed == NemotronBackend.C2 -> NemotronBackend.REVISION
            else -> DiarizationModelStore.REVISION
        }
        val timestampSource = when {
            output.tokenTimedWindows > 0 && output.untimedWindows == 0 -> "asr_token_timestamps"
            output.tokenTimedWindows > 0 -> "asr_token_timestamps_and_input_windows"
            diarization == null -> "input_windows"
            output.tokenTimedWindows == 0 -> "diarization_boundaries_and_input_windows"
            else -> "input_windows"
        }
        val warnings = listOfNotNull(warning, if (output.tokenTimedWindows > 0)
                "Время слов — по меткам токенов ASR (шаг 40 мс), не точное выравнивание."
            else "Интервалы фрагментов, не пословное выравнивание.",
            if (output.decodedWindows == 0) "Сегментация не обнаружила речевых окон; ASR не запускался." else null,
            if (output.decodedWindows > 0 && output.segments.isEmpty()) "ASR не вернул текста." else null,
            if (diarization == null) "Говорящие не определены." else null)
        val document = TranscriptDocument(output.segments.toList(), output.audioMs, TranscriptProvenance(
            output.modelId, output.modelRevision, timestampSource, speakerSource,
            BuildConfig.SHERPA_RUNTIME_SHA256), warnings)
        val details = (if (output.decodedWindows == 0) "Речевые окна не обнаружены; ASR не запускался. " else
                if (output.segments.isEmpty()) "ASR не вернул текста. " else "ASR вернул ${output.segments.size} фрагментов. ") +
                "Аудио: ${output.audioMs} мс; загрузка ${output.loadMs} мс; обработка ${output.decodeMs} мс. " +
                (if (diarization == null) "Диаризация недоступна. ASR без говорящих. " else
                    "Диаризация ${backendUsed?.uppercase()}: ${diarization.turns.filter { it.attributionEligible }.map { it.speakerId }.distinct().size} кластеров, ${diarization.processMs} мс. ") +
                (warning ?: "")
        android.util.Log.i("NeuroStenoMetrics", details)
        val named = (mutable.value.sourceName ?: "Стенограмма").replace(Regex("\\.(wav|mp3|m4a|ogg|opus|flac|aac|amr|3gp|webm)$", RegexOption.IGNORE_CASE), "")
        // A recording that only has a date for a name gets its topic (most repeated meaningful words) in front of it.
        // A file the user named themselves keeps its name.
        val topic = if (named.startsWith("Запись ") || named == "Аудиофайл") TopicTitle.suggest(document.segments) else null
        val title = if (topic != null) topic + " · " + named.removePrefix("Запись ") else named
        val saved = withContext(Dispatchers.IO) { history.save(title, document) }
        // The transcript is kept; the audio copy is not needed any more.
        discardSnapshot(mutable.value.source)
        mutable.value = mutable.value.copy(source = null, sourceName = null, segments = document.segments, document = document,
            sourceDurationMs = output.audioMs, speakerSource = speakerSource, timestampSource = timestampSource,
            current = saved, history = listOf(saved) + mutable.value.history, details = details, message = READY)
    }

    private suspend fun recognizeBlock(audio: PcmAudio, model: File):
        Triple<AsrOutput, DiarizationOutput?, Pair<String?, String?>> {
        val context = currentCoroutineContext()
        val app = getApplication<Application>()
        if (audio.samples.all { it == 0f })
            return Triple(AsrOutput(emptyList(), audio.durationMs, 0, 0),
                DiarizationOutput(emptyList(), 0, 0, emptyList()), "digital-silence" to null)
        var warning: String? = null
        var backendUsed: String? = null
        var speakers: DiarizationOutput? = null

        if (BuildConfig.NEMOTRON_PROTOTYPE) {
            try {
                mutable.value = mutable.value.copy(message = "Готовлю определение говорящих…")
                // The product APK carries a pinned ZIP. The research prototype can
                // use C0 if the C2 ZIP is not bundled in its ordinary UI.
                val c2 = NemotronBackend.current(app.filesDir)
                    ?: app.assets.open("nemotron.zip").use { NemotronBackend.install(app.filesDir, it) }
                context.ensureActive()
                mutable.value = mutable.value.copy(message = "Определяю, кто говорит…", stage = 2)
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
                    mutable.value = mutable.value.copy(message = "Определяю, кто говорит…", stage = 2)
                    speakers = IsolatedDiarization.process(app, audio, c0Model, backend = NemotronBackend.C0)
                    backendUsed = NemotronBackend.C0
                } catch (e: CancellationException) { throw e }
                catch (e: Exception) {
                    warning = listOfNotNull(warning, e.message ?: "Диаризация C0 недоступна")
                        .joinToString(" ")
                }
            }
        }
        val progress: (Int, Int) -> Unit = { index, count ->
            mutable.value = mutable.value.copy(progress = index.toFloat() / count, stage = 3,
                message = "Расшифровываю речь: часть $index из $count")
        }
        val english = if (BuildConfig.ENGLISH_AUTO) {
            mutable.value = mutable.value.copy(message = "Определяю язык записи…", stage = 3)
            val englishModel = EnglishModelStore.ensure(app) { context.ensureActive() }
            val language = WhisperEnglish.detect(audio, englishModel,
                speakers?.windows ?: DiarizationTimeline.windows(emptyList(), audio.durationMs)) { context.ensureActive() }
            if (language == "en") WhisperEnglish.transcribe(audio, englishModel,
                speakers?.turns.orEmpty(), speakers?.windows, { context.ensureActive() }, progress)
            else null
        } else null
        val asr = if (english != null) AsrOutput(english.segments, audio.durationMs,
            english.loadMs, english.decodeMs, english.windows, untimedWindows = english.windows,
            modelId = WhisperEnglish.ID, modelRevision = WhisperEnglish.REVISION)
        else OfflineAsr.transcribe(audio, model, { context.ensureActive() }, progress,
            turns = speakers?.turns.orEmpty(), speechWindows = speakers?.windows)
        return Triple(asr, speakers, backendUsed to warning)
    }

    /** Long-file fallback keeps bounded memory and every block's text. Local C2 slot
     * numbers are not global identities; do not invent continuity across independent runs. */
    private suspend fun recognizeLong(pcm: PcmFileAudio, model: File):
        Triple<AsrOutput, DiarizationOutput?, Pair<String?, String?>> {
        val context = currentCoroutineContext()
        val segments = mutableListOf<TranscriptSegment>()
        val ids = linkedSetOf<String>()
        val revisions = linkedSetOf<String>()
        val warnings = linkedSetOf<String>()
        var load = 0L; var decode = 0L
        var windows = 0; var timed = 0; var untimed = 0
        var start = 0L
        while (start < pcm.durationMs) {
            context.ensureActive()
            var end = minOf(start + 300_000, pcm.durationMs)
            if (end < pcm.durationMs) {
                val boundary = pcm.read(end - 3000, end) { context.ensureActive() }
                end = end - 3000 + QuietCuts.phraseCut(boundary.samples) / 16
            }
            if (pcm.durationMs - end in 1..99) end = pcm.durationMs
            mutable.value = mutable.value.copy(message = "Обработка длинной записи: ${clock(start)} из ${clock(pcm.durationMs)}", stage = 1)
            val block = pcm.read(start, end) { context.ensureActive() }
            val first = block.samples.indexOfFirst { it != 0f }
            if (first < 0) { start = end; continue }
            val last = block.samples.indexOfLast { it != 0f }
            // Only exact digital silence can be discarded, never a volume threshold.
            val localStart = (first / 16L - 1000).coerceAtLeast(0)
            val localEnd = (last / 16L + 1001).coerceAtMost(block.durationMs)
            val trimmed = PcmAudio(block.samples.copyOfRange((localStart * 16).toInt(),
                minOf((localEnd * 16).toInt(), block.samples.size)), 16000)
            val (asr, _, processing) = recognizeBlock(trimmed, model)
            val offset = start + localStart
            segments += asr.segments.map { it.copy(startMs = it.startMs + offset, endMs = it.endMs + offset,
                speakerId = null, attributionReliable = false, overlapSpeakers = emptyList()) }
            ids += asr.modelId; revisions += asr.modelRevision
            processing.second?.let { warnings += it }
            load += asr.loadMs; decode += asr.decodeMs
            windows += asr.decodedWindows; timed += asr.tokenTimedWindows; untimed += asr.untimedWindows
            start = end
        }
        warnings += "Длинная запись обработана блоками. Сквозное сопоставление говорящих между блоками пока недоступно; текст сохранён без назначения говорящих."
        return Triple(AsrOutput(segments, pcm.durationMs, load, decode, windows, timed, untimed,
            ids.joinToString("+").ifEmpty { AsrModelSpec.ACTIVE.id },
            revisions.joinToString("+").ifEmpty { AsrModelSpec.ACTIVE.revision }), null,
            "long-file" to warnings.joinToString(" "))
    }

    fun prepareExport(format: String) {
        val document = requireNotNull(mutable.value.document) { "Нет распознанной стенограммы" }
        pendingExport = format to document.export(format, currentNames(), currentEdits())
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

    val recordingLevel: Float get() = recorder?.level ?: 0f

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
            mutable.value = mutable.value.copy(message = "Идёт запись. Максимум — ${PcmFileAudio.MAX_FILE_LABEL}. Предыдущий результат сохранён до успешной остановки.")
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
                val deadline = System.nanoTime() + PcmFileAudio.MAX_FILE_SECONDS * 1_000_000_000L
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
            val stamp = java.text.SimpleDateFormat("d MMM, HH:mm", java.util.Locale("ru")).format(java.util.Date())
            mutable.value = mutable.value.copy(source = Uri.fromFile(file), sourceName = "Запись $stamp", current = null,
                sourceDurationMs = (file.length() - 44) * 1000 / 32000, segments = emptyList(), document = null,
                speakerSource = "not_run", timestampSource = "input_windows",
                message = "Запись сохранена.")
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

    /** Drops audio that was not recognised (cancelled or failed). Only app-owned copies are deleted, never a user's file. */
    fun discardSource() {
        if (mutable.value.busy || recording.value) return
        val uri = mutable.value.source
        if (uri?.scheme == "file") {
            val file = File(uri.path ?: "")
            val app = getApplication<Application>()
            val ownedCopy = file.parentFile == File(app.cacheDir, "audio-input") ||
                (file.parentFile == app.filesDir && file.name.matches(Regex("recording_\\d+\\.wav")))
            if (ownedCopy) file.delete()
        }
        mutable.value = mutable.value.copy(source = null, sourceName = null, sourceDurationMs = null, message = READY)
    }

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
        const val READY = "Готово. Запишите разговор или откройте аудиофайл."
        val KIT_ASR_ZIP = AsrModelSpec.ACTIVE.zipName
        const val KIT_DIARIZATION_ZIP = "diarization.zip"
    }
}
