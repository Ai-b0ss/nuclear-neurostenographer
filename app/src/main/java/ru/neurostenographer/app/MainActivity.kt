package ru.neurostenographer.app

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import ru.neurostenographer.core.TranscriptExport
import ru.neurostenographer.core.TranscriptSegment
import java.io.File

/** This UI deliberately does not claim that speech inference is implemented. */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MaterialTheme { ApplicationScreen() } }
    }

    @Composable
    private fun ApplicationScreen() {
        var recorder by remember { mutableStateOf<RecordWav?>(null) }
        var recording by remember { mutableStateOf(false) }
        var selectedFile by remember { mutableStateOf<String?>(null) }
        var message by remember { mutableStateOf("ASR и диаризация пока не подключены.") }
        var showExample by remember { mutableStateOf(false) }
        val example = remember { listOf(
            TranscriptSegment(1000L, 3200L, "Говорящий 1", "Начнём обсуждение?", attributionReliable = true),
            TranscriptSegment(3500L, 5200L, "Говорящий 2", "Да, давайте.", attributionReliable = true),
            TranscriptSegment(5600L, 7200L, "Говорящий 1", "Отлично.", attributionReliable = true)
        ) }
        val importAudio = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
            if (uri != null) {
                selectedFile = uri.toString()
                message = "Файл выбран. Распознавание пока недоступно."
            }
        }
        val exportExample = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/plain")) { uri ->
            if (uri != null) {
                try {
                    contentResolver.openOutputStream(uri)?.use { output ->
                        output.write(TranscriptExport.txt(example).toByteArray(Charsets.UTF_8))
                    }
                    message = "Экспортирован только демонстрационный пример."
                } catch (e: Exception) {
                    message = e.message ?: "Ошибка экспорта"
                }
            }
        }
        val micPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
            message = if (ok) "Микрофон разрешён. Можно записывать." else "Разрешение микрофона отклонено."
        }

        Scaffold { padding ->
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding).padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                item { Text("Нейро-стенографист", style = MaterialTheme.typography.headlineMedium) }
                item { Text("Nuclear IT Hack · полностью офлайн", style = MaterialTheme.typography.labelLarge) }
                item { Text("Запись остаётся на смартфоне. Интернет не требуется.") }
                item {
                    Button(onClick = {
                        if (recording) {
                            try {
                                val file = recorder?.stop()
                                selectedFile = file?.absolutePath
                                message = "Запись сохранена: " + (file?.name ?: "неизвестно")
                            } catch (e: Exception) {
                                message = e.message ?: "Не удалось остановить запись"
                            } finally {
                                recorder = null
                                recording = false
                            }
                        } else if (ContextCompat.checkSelfPermission(
                                this@MainActivity, Manifest.permission.RECORD_AUDIO
                            ) != PackageManager.PERMISSION_GRANTED) {
                            micPermission.launch(Manifest.permission.RECORD_AUDIO)
                        } else {
                            try {
                                val file = File(filesDir, "recording_" + System.currentTimeMillis() + ".wav")
                                val r = RecordWav(file)
                                r.start()
                                recorder = r
                                recording = true
                                message = "Идёт запись. Нажмите «Остановить»."
                            } catch (e: Exception) {
                                message = e.message ?: "Микрофон недоступен"
                            }
                        }
                    }) {
                        Text(if (recording) "Остановить запись" else "Записать разговор")
                    }
                }
                item {
                    OutlinedButton(onClick = { importAudio.launch(arrayOf("audio/*")) }) {
                        Text("Импортировать аудио")
                    }
                }
                item { Text(selectedFile ?: "Файл не выбран", style = MaterialTheme.typography.bodySmall) }
                item { Text(message, color = MaterialTheme.colorScheme.secondary) }
                item { HorizontalDivider() }
                item { Text("Стенограмма", style = MaterialTheme.typography.titleLarge) }
                item { Text("Реальное распознавание будет подключено через sherpa-onnx и русскую ASR-модель.") }
                item {
                    TextButton(onClick = { showExample = !showExample }) {
                        Text(if (showExample) "Скрыть пример" else "Показать пример")
                    }
                }
                if (showExample) {
                    item {
                        Text("ДЕМОНСТРАЦИЯ — НЕ РАСПОЗНАННАЯ ЗАПИСЬ",
                            color = MaterialTheme.colorScheme.error)
                    }
                    items(example) { segment ->
                        Card(modifier = Modifier.fillMaxWidth()) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                Text(
                                    (segment.speakerId ?: "Не определён") + " · " +
                                        (segment.startMs / 1000) + "–" + (segment.endMs / 1000) + " c",
                                    style = MaterialTheme.typography.labelMedium
                                )
                                Text(segment.text)
                            }
                        }
                    }
                    item {
                        OutlinedButton(onClick = { exportExample.launch("example-transcript.txt") }) {
                            Text("Экспорт примера TXT")
                        }
                    }
                }
            }
        }
    }
}
