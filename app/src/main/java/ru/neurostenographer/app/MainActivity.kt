package ru.neurostenographer.app

import android.Manifest
import android.content.pm.PackageManager
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle

class MainActivity : ComponentActivity() {
    private val model: TranscriptionViewModel by viewModels()
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MaterialTheme { ApplicationScreen() } }
    }
    override fun onStop() {
        if (!isChangingConfigurations && model.recording.value) model.stopRecording()
        super.onStop()
    }
    @Composable
    @OptIn(ExperimentalLayoutApi::class)
    private fun ApplicationScreen() {
        val state by model.state.collectAsState()
        val recording by model.recording.collectAsState()
        var notice by remember { mutableStateOf("") }
        val importAudio = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let(model::select) }
        val importModel = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let(model::install) }
        val importSpeakers = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let(model::installDiarization) }
        val exportTxt = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/plain"), model::finishExport)
        val exportJson = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json"), model::finishExport)
        val exportSrt = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/x-subrip"), model::finishExport)
        val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
            if (ok && lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) model.startRecording()
            else notice = if (ok) "Вернитесь в приложение и нажмите запись." else "Разрешение микрофона отклонено."
        }
        Scaffold { padding ->
            LazyColumn(modifier = Modifier.fillMaxSize().padding(padding).padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)) {
                item { Text("Нейро-стенографист", style = MaterialTheme.typography.headlineMedium) }
                item { Text("GigaAM v3 · экспериментальный офлайн ASR") }
                item { Text("WAV и системные аудиокодеки (экспериментально): 1–2 канала, 8–48 кГц, до 120 секунд, файл до 24 МБ. Запись и распознавание остаются на устройстве.") }
                item {
                    OutlinedButton(enabled = !state.busy && !recording,
                        onClick = { importModel.launch(arrayOf("application/zip", "application/octet-stream")) }) {
                        Text(if (state.modelReady) "Заменить модель ZIP" else "Установить модель ZIP")
                    }
                    Text("Подготовьте gigaam-v3.zip по инструкции README и перенесите на телефон (225 МБ).",
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
                item { Text(state.message, color = MaterialTheme.colorScheme.secondary) }
                if (notice.isNotEmpty()) item { Text(notice) }
                if (state.busy) item {
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                    TextButton(onClick = model::cancel) { Text("Отменить после текущего шага") }
                }
                item { HorizontalDivider() }
                item { Text("Стенограмма", style = MaterialTheme.typography.titleLarge) }
                item { Text("Время — границы модельных реплик/входных фрагментов до 20 с, не слов. Speaker — кластер голоса в этой записи, не личность. Перекрытия и короткие участки могут остаться неопределёнными.") }
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
