package ru.neurostenographer.app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.SystemClock
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.delay
import androidx.lifecycle.Lifecycle

class MainActivity : ComponentActivity() {
    private val model: TranscriptionViewModel by viewModels()
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MaterialTheme { ApplicationScreen() } }
    }
    override fun onStop() {
        // With the foreground service the recording survives; without it the system
        // may cut the microphone, so stop and keep what was recorded.
        if (!isChangingConfigurations && model.recording.value && !RecordingService.active) model.stopRecording()
        super.onStop()
    }
    @Composable
    @OptIn(ExperimentalLayoutApi::class)
    private fun ApplicationScreen() {
        val state by model.state.collectAsState()
        val recording by model.recording.collectAsState()
        // A long recording must not stop because the screen timed out mid-processing.
        val view = LocalView.current
        DisposableEffect(view, state.busy, recording) {
            view.keepScreenOn = state.busy || recording
            onDispose { view.keepScreenOn = false }
        }
        val elapsed by produceState(0L, recording) {
            if (!recording) value = 0L else {
                val started = SystemClock.elapsedRealtime()
                while (true) { value = (SystemClock.elapsedRealtime() - started) / 1000; delay(1000) }
            }
        }
        var notice by remember { mutableStateOf("") }
        val importAudio = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let(model::select) }
        val importModel = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let(model::install) }
        val importSpeakers = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let(model::installDiarization) }
        val exportTxt = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/plain"), model::finishExport)
        val exportJson = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json"), model::finishExport)
        val exportSrt = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/x-subrip"), model::finishExport)
        val notifications = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {}
        val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
            if (ok && Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(this@MainActivity,
                    Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                // Optional: the service runs without it, only its notification stays hidden.
                notifications.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
            if (ok && lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) model.startRecording()
            else notice = if (ok) "Вернитесь в приложение и нажмите запись." else "Разрешение микрофона отклонено."
        }
        Scaffold { padding ->
            LazyColumn(modifier = Modifier.fillMaxSize().padding(padding).padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)) {
                item { Text("Нейро-стенографист", style = MaterialTheme.typography.headlineMedium) }
                item { Text(if (state.c2Supported) "GigaAM v3 + Nemotron C2 · полностью офлайн"
                    else "GigaAM v3 · экспериментальный офлайн ASR") }
                item { Text("WAV и системные аудиокодеки (экспериментально): 1–2 канала, 8–48 кГц, до 20 минут. Запись и распознавание остаются на устройстве.") }
                // Status, errors and progress stay at the top: the screen is a long list and a
                // message lost in the middle hides a failed operation or a running recording.
                if (recording) item {
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Text("● Запись: ${clock(elapsed)} из ${clock(ru.neurostenographer.core.PcmWav.MAX_SECONDS.toLong())}",
                                style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.error)
                            Text(if (RecordingService.active) "Приложение можно свернуть: запись продолжится, в шторке есть уведомление."
                                else "Не сворачивайте приложение: фоновая запись недоступна, при сворачивании запись остановится и сохранится.",
                                style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
                item { Text(state.message, color = MaterialTheme.colorScheme.secondary) }
                if (notice.isNotEmpty()) item { Text(notice) }
                if (state.busy) item {
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                    TextButton(onClick = model::cancel) { Text("Отменить после текущего шага") }
                }
                if (!state.modelReady) item {
                    Text("Модель распознавания не установлена: без неё распознавание недоступно.",
                        color = MaterialTheme.colorScheme.error)
                } else if (!state.diarizationReady && !state.c2Supported) item {
                    Text("Модели говорящих не установлены: стенограмма будет без разделения по говорящим.",
                        color = MaterialTheme.colorScheme.secondary)
                }
                if (state.c2Supported) item {
                    Text(if (state.expectedSpeakers > 0)
                        "При заданном числе участников используется установленная модель разделения голосов. Чтобы снова использовать Nemotron C2, выберите «Авто»."
                    else "Nemotron C2 доступен офлайн. При распознавании модель проверяется по SHA-256; при её ошибке используется резервный C0 (если установлен).",
                        style = MaterialTheme.typography.bodySmall)
                }
                item {
                    OutlinedButton(enabled = !state.busy && !recording,
                        onClick = { importModel.launch(arrayOf("application/zip", "application/octet-stream")) }) {
                        Text(if (state.modelReady) "Заменить модель ZIP" else "Установить модель ZIP")
                    }
                    Text("gigaam-v3.zip (225 МБ) — по инструкции README. Либо положите оба ZIP в папку комплекта через adb (docs/OFFLINE_KIT.md): установка пройдёт сама при запуске.",
                        style = MaterialTheme.typography.bodySmall)
                }
                item {
                    OutlinedButton(enabled = !state.busy && !recording,
                        onClick = { importSpeakers.launch(arrayOf("application/zip", "application/octet-stream")) }) {
                        Text(if (state.diarizationReady) "Заменить модели говорящих ZIP" else "Установить модели говорящих ZIP")
                    }
                    Text("diarization.zip (46 МБ): pyannote + ERes2Net. Экспериментально: при сбое диаризации ASR продолжится без говорящих.",
                        style = MaterialTheme.typography.bodySmall)
                }
                item {
                    Button(enabled = !state.busy, onClick = {
                        if (recording) model.stopRecording()
                        else if (ContextCompat.checkSelfPermission(this@MainActivity, Manifest.permission.RECORD_AUDIO)
                            == PackageManager.PERMISSION_GRANTED) model.startRecording()
                        else permission.launch(Manifest.permission.RECORD_AUDIO)
                    }) { Text(if (recording) "Остановить запись" else "Записать разговор") }
                }
                item {
                    OutlinedButton(enabled = !state.busy && !recording,
                        onClick = { importAudio.launch(arrayOf("audio/*", "application/ogg", "application/octet-stream")) }) { Text("Импортировать аудио") }
                }
                item { Text(state.sourceDurationMs?.let { "WAV · ${ru.neurostenographer.core.TranscriptExport.time(it)}" }
                    ?: if (state.source != null) "WAV выбран" else "WAV не выбран", style = MaterialTheme.typography.bodySmall) }
                if (state.diarizationReady) item {
                    Text("Число участников записи", style = MaterialTheme.typography.titleSmall)
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        for (count in listOf(-1, 2, 3, 4)) {
                            FilterChip(selected = state.expectedSpeakers == count,
                                enabled = !state.busy && !recording,
                                onClick = { model.setExpectedSpeakers(count) },
                                label = { Text(if (count == -1) "Авто" else count.toString()) })
                        }
                    }
                    Text("Укажите число, только если знаете его точно. Неверное число может ухудшить разделение голосов.",
                        style = MaterialTheme.typography.bodySmall)
                }
                item {
                    TextButton(enabled = !state.busy && !recording, onClick = model::clearLocalAudio) {
                        Text("Удалить локальное аудио и результат")
                    }
                    Text("Удаляет записи и временные копии приложения. Экспортированные документы нужно удалить отдельно.",
                        style = MaterialTheme.typography.bodySmall)
                }
                item {
                    Button(enabled = state.source != null && state.modelReady && !state.busy && !recording,
                        onClick = model::transcribe) { Text("Распознать офлайн") }
                }
                item { HorizontalDivider() }
                item { Text("Стенограмма", style = MaterialTheme.typography.titleLarge) }
                item { Text("Время — границы реплик (до 60 с) и входных фрагментов (до 20 с), не слов. Speaker — предположение модели, не личность: разные голоса могут объединиться, один голос — разделиться. Проверьте распределение реплик вручную. Перекрытия и короткие участки могут остаться неопределёнными.") }
                items(state.segments) { segment ->
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Text("${segment.speakerId ?: "Говорящий не определён"} · ${ru.neurostenographer.core.TranscriptExport.time(segment.startMs)}–${ru.neurostenographer.core.TranscriptExport.time(segment.endMs)}" +
                                if (segment.overlappingSpeech) " · перекрытие речи" else "",
                                style = MaterialTheme.typography.labelMedium)
                            Text(segment.text)
                        }
                    }
                }
                if (state.document != null) item {
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        for (format in listOf("txt", "json", "srt")) {
                            OutlinedButton(enabled = !state.busy && !recording, onClick = {
                                model.prepareExport(format)
                                when (format) {
                                    "json" -> exportJson.launch("transcript.json")
                                    "srt" -> exportSrt.launch("transcript.srt")
                                    else -> exportTxt.launch("transcript.txt")
                                }
                            }) { Text(format.uppercase()) }
                        }
                    }
                }
            }
        }
    }
}

private fun clock(seconds: Long) = "%02d:%02d".format(seconds / 60, seconds % 60)
