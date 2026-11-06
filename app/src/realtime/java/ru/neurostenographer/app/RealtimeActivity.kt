package ru.neurostenographer.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import java.io.File

/** Live transcription: words appear after each phrase while recording; speakers are refined over the whole
 * recording after Stop (same C2 pass as file import). The transcript is then saved to the shared history. */
class RealtimeActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Recover only feature-owned unfinished WAV headers; existing history is untouched.
        RealtimeService.recover(filesDir)
        if (RealtimeService.view.value.status == "IDLE") {
            File(filesDir, "realtime").listFiles().orEmpty().filter { it.isDirectory && it.name.matches(Regex("\\d+")) }
                .maxByOrNull { it.name }?.let { dir ->
                    val audio = File(dir, "capture.wav")
                    val done = File(dir, "transcript-current.json").isFile
                    if (!done && audio.length() >= 3244) RealtimeService.view.value = RealtimeView("RECOVERED_WAV",
                        directory = dir.absolutePath, audioMs = (audio.length() - 44) / 32)
                }
        }
        setContent { StenoTheme { LiveScreen() } }
    }

    @Composable
    private fun LiveScreen() {
        val state by RealtimeService.view.collectAsState()
        val start = {
            runCatching { ContextCompat.startForegroundService(this, Intent(this, RealtimeService::class.java)) }
                .onFailure { RealtimeService.view.value = RealtimeView("FAILED: не удалось начать запись") }
            Unit
        }
        val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
            if (ok && lifecycle.currentState.isAtLeast(androidx.lifecycle.Lifecycle.State.STARTED)) start()
            else RealtimeService.view.value = RealtimeView(if (ok) "IDLE" else "FAILED: разрешение микрофона отклонено")
        }
        var exportText by remember { mutableStateOf("") }
        val export = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri ->
            if (uri != null) contentResolver.openOutputStream(uri, "wt")?.use { it.write(exportText.toByteArray()) }
        }
        val status = state.status
        val recording = status in listOf("LOADING", "RUNNING", "CAPTURE_ONLY")
        val busy = recording || status == "FINALIZING"
        val complete = status.startsWith("COMPLETE")
        val segments = state.document?.segments.orEmpty()
        val list = rememberLazyListState()
        LaunchedEffect(segments.size) { if (segments.isNotEmpty()) list.animateScrollToItem(segments.size - 1) }

        Scaffold { padding ->
            Column(Modifier.fillMaxSize().padding(padding).padding(horizontal = 16.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    TextButton(onClick = { finish() }, enabled = !busy) { Text("← Назад") }
                    Spacer(Modifier.width(4.dp))
                    Text("Живая расшифровка", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                }
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                    elevation = CardDefaults.cardElevation(1.dp)) {
                    Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(clock(state.audioMs), style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.Bold,
                                color = if (recording) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface)
                            Spacer(Modifier.width(12.dp))
                            Text(statusText(status), style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        if (status == "LOADING" || status == "FINALIZING") LinearProgressIndicator(Modifier.fillMaxWidth())
                        if (!busy) Button(onClick = {
                            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) start()
                            else permission.launch(Manifest.permission.RECORD_AUDIO)
                        }, modifier = Modifier.fillMaxWidth().height(56.dp)) {
                            Text(if (complete) "Новая запись" else "Начать запись", style = MaterialTheme.typography.titleMedium)
                        }
                        if (recording) Button(onClick = { service("STOP") }, modifier = Modifier.fillMaxWidth().height(56.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)) {
                            Text("Остановить", style = MaterialTheme.typography.titleMedium)
                        }
                        if (status == "FINALIZING") TextButton(onClick = { service("CANCEL") }) {
                            Text("Пропустить уточнение (запись и текст сохранятся)")
                        }
                        if (complete) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(onClick = { finish() }, modifier = Modifier.weight(1f)) { Text("Открыть в истории") }
                            OutlinedButton(onClick = { exportText = state.document!!.export("json"); export.launch("live.json") },
                                enabled = state.document != null, modifier = Modifier.weight(1f)) { Text("Экспорт JSON") }
                        }
                        batchFallback(state)
                    }
                }
                if (recording && segments.isNotEmpty()) Text("Говорящие предварительные: после остановки они уточняются по всей записи.",
                    style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (segments.isEmpty()) Text(
                    if (recording) "Говорите — текст появится после каждой фразы (обычно через 1–2 с)."
                    else "Распознавание и разделение говорящих идут на телефоне, без интернета.",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                LazyColumn(state = list, modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    items(segments) { Reply(it, emptyMap(), "", onSpeaker = {}) }
                }
            }
        }
    }

    /** Only when live inference did not finish: the saved WAV can still go through file recognition. */
    @Composable
    private fun batchFallback(state: RealtimeView) {
        if (state.status !in listOf("CANCELLED", "CAPTURE_INTERRUPTED", "RECOVERED_WAV") && !state.status.startsWith("FAILED")) return
        val captured = state.directory?.let { File(it, "capture.wav") } ?: return
        val finalized = File(captured.parentFile, "capture-finalized.txt").isFile || File(captured.parentFile, "recovered.txt").isFile
        if (!finalized) return
        if (state.audioMs > 20 * 60 * 1000) {
            Text("Запись длиннее 20 минут сохранена; обычное распознавание файла ограничено 20 минутами.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            return
        }
        OutlinedButton(onClick = {
            startActivity(Intent(this, MainActivity::class.java).setAction("ru.neurostenographer.REALTIME_BATCH")
                .setData(android.net.Uri.fromFile(captured)).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP))
            finish()
        }, modifier = Modifier.fillMaxWidth()) { Text("Распознать сохранённую запись как файл") }
    }

    private fun service(action: String) {
        startService(Intent(this, RealtimeService::class.java).setAction(action))
    }

    private fun statusText(status: String) = when {
        status == "IDLE" -> "Готов к записи"
        status == "LOADING" -> "Загружаю модели…"
        status == "RUNNING" -> "Слушаю"
        status == "CAPTURE_ONLY" -> "Идёт запись"
        status == "FINALIZING" -> "Уточняю говорящих по всей записи…"
        status == "COMPLETE" -> "Готово · сохранено в истории"
        status == "COMPLETE_PROVISIONAL" -> "Готово · говорящие предварительные"
        status == "COMPLETE_UNKNOWN_SPEAKERS" -> "Готово · без разделения говорящих"
        status == "CANCELLED" -> "Обработка остановлена · запись сохранена"
        status == "CAPTURE_INTERRUPTED" -> "Запись прервалась · сохранённое доступно"
        status == "RECOVERED_WAV" -> "Найдена незавершённая запись"
        status.startsWith("FAILED") -> "Ошибка: " + status.removePrefix("FAILED").trimStart(':', ' ').ifBlank { "см. запись" }
        else -> status
    }
}
