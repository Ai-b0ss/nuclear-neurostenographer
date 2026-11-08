package ru.neurostenographer.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.neurostenographer.core.TopicTitle
import ru.neurostenographer.core.TranscriptExport
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

    private fun liveBusy() = RealtimeService.view.value.status in listOf("LOADING", "RUNNING", "FINALIZING", "CAPTURE_ONLY")

    override fun onStart() {
        super.onStart()
        if (!liveBusy()) RealtimePreload.start(this)
    }

    override fun onStop() {
        // Leaving the screen without a live session frees the ~1 GB of preloaded models.
        if (!liveBusy()) RealtimePreload.release()
        super.onStop()
    }

    @OptIn(ExperimentalMaterial3Api::class)
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
        val micLevel by produceState(0f, recording) {
            while (recording) { value = RealtimeCapture.microphoneLevel; kotlinx.coroutines.delay(50) }
            value = 0f
        }
        val segments = state.document?.segments.orEmpty()
        val list = rememberLazyListState()
        // Stop answers at once: the service needs a moment to report FINALIZING, the screen must not look frozen meanwhile.
        var stopping by remember { mutableStateOf(false) }
        LaunchedEffect(status) { stopping = false }
        LaunchedEffect(segments.size) { if (segments.isNotEmpty()) list.animateScrollToItem(segments.size - 1) }
        // After a session ends, the next one should start without a model-loading wait as well.
        LaunchedEffect(busy) { if (!busy) RealtimePreload.start(this@RealtimeActivity) }
        val red = MaterialTheme.colorScheme.error

        Scaffold(containerColor = MaterialTheme.colorScheme.background, topBar = {
            TopAppBar(title = { Text("Живая расшифровка", fontWeight = FontWeight.SemiBold,
                maxLines = 1, overflow = TextOverflow.Ellipsis) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
                navigationIcon = { IconButton(onClick = { finish() }, enabled = !busy) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Назад") } })
        }) { padding ->
            // Text panel on top (always there, grows with the conversation), controls at the bottom under the thumb.
            Column(Modifier.fillMaxSize().padding(padding).padding(horizontal = 16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Surface(Modifier.weight(1f).fillMaxWidth(), shape = RoundedCornerShape(24.dp), color = MaterialTheme.colorScheme.surface) {
                    if (segments.isEmpty()) {
                        Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center,
                            horizontalAlignment = Alignment.CenterHorizontally) {
                            if (recording) {
                                Text(when (status) {
                                    "LOADING" -> "Запись уже идёт. Подготавливаю распознавание…"
                                    "CAPTURE_ONLY" -> "Звук сохраняется. После остановки запись можно расшифровать отдельно."
                                    else -> "Текст появляется после каждой фразы. Говорите в обычном темпе."
                                },
                                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    textAlign = TextAlign.Center)
                            } else Text(
                                if (complete) "Речь не распознана." else "Здесь появится текст разговора по ходу записи.\nВсё обрабатывается на телефоне, без интернета. Одна живая запись — до 1 часа.",
                                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                                textAlign = TextAlign.Center)
                        }
                    } else {
                        LazyColumn(state = list, modifier = Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(18.dp),
                            contentPadding = PaddingValues(16.dp)) {
                            items(segments) { Reply(it, emptyMap(), "", onSpeaker = {}) }
                        }
                    }
                }
                // Keep the actual microphone level visible even after live text begins.
                if (recording) {
                    Spacer(Modifier.height(8.dp))
                    VoiceWaveform(micLevel, MaterialTheme.colorScheme.primary,
                        modifier = Modifier.fillMaxWidth().height(56.dp))
                }
                Spacer(Modifier.height(10.dp))
                if (recording && segments.isNotEmpty()) Text("Говорящие предварительные: после остановки они уточняются по всей записи.",
                    style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
                Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween) {
                    Column(Modifier.weight(1f)) {
                        Text(clock(state.audioMs), fontSize = 40.sp, fontWeight = FontWeight.Light,
                            color = if (recording) red else MaterialTheme.colorScheme.onSurface)
                        Text(if (stopping) "Останавливаю…" else statusText(status), style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                        if (status == "LOADING" || status == "FINALIZING" || stopping) {
                            Spacer(Modifier.height(6.dp))
                            LinearProgressIndicator(Modifier.fillMaxWidth(0.8f).clip(RoundedCornerShape(50)))
                        }
                    }
                    Spacer(Modifier.width(12.dp))
                    if (!busy) {
                        Column(Modifier.clip(RoundedCornerShape(24.dp)).clickable {
                            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) start()
                            else permission.launch(Manifest.permission.RECORD_AUDIO)
                        }.padding(6.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                            Box(Modifier.size(76.dp).background(MaterialTheme.colorScheme.primary, CircleShape), contentAlignment = Alignment.Center) {
                                MicGlyph(MaterialTheme.colorScheme.onPrimary, 34.dp)
                            }
                            Spacer(Modifier.height(6.dp))
                            Text(if (complete) "Новая запись" else "Начать запись", style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.SemiBold)
                        }
                    } else if (recording) {
                        Column(Modifier.clip(RoundedCornerShape(24.dp)).clickable(enabled = !stopping) {
                            stopping = true
                            service("STOP")
                        }.padding(6.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                            Box(Modifier.size(76.dp).background(red, CircleShape), contentAlignment = Alignment.Center) {
                                Box(Modifier.size(24.dp).background(Color.White, RoundedCornerShape(6.dp)))
                            }
                            Spacer(Modifier.height(6.dp))
                            Text("Остановить", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold, color = red)
                        }
                    }
                }
                if (status == "FINALIZING") TextButton(onClick = { service("CANCEL") }) {
                    Text("Пропустить уточнение (запись и текст сохранятся)", textAlign = TextAlign.Center)
                }
                if (complete) Row(Modifier.padding(bottom = 4.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { finish() }, modifier = Modifier.weight(1f)) { Text("В историю", textAlign = TextAlign.Center) }
                    OutlinedButton(onClick = {
                        val doc = state.document!!
                        exportText = doc.export("json-contest")
                        // The file is named after what was said, not «live»: topic words + date, like the saved transcript.
                        val topic = TopicTitle.suggest(doc.segments)
                        val stamp = java.text.SimpleDateFormat("yyyy-MM-dd HH-mm", java.util.Locale("ru")).format(java.util.Date())
                        export.launch(TranscriptExport.fileBase((topic ?: "Живая запись") + " " + stamp) + ".json")
                    }, enabled = state.document != null, modifier = Modifier.weight(1f)) { Text("Сохранить JSON", textAlign = TextAlign.Center) }
                }
                batchFallback(state)
                Spacer(Modifier.height(8.dp))
            }
        }
    }

    /** Reuse the full file pipeline after live capture, without holding both
     * live native models and the FDDT encoder in memory at the same time.
     */
    @Composable
    private fun batchFallback(state: RealtimeView) {
        val refineOverlap = BuildConfig.FDDT_HYBRID && state.status.startsWith("COMPLETE") &&
            state.document?.segments?.any { it.overlappingSpeech } == true
        if (!refineOverlap && state.status !in listOf("CANCELLED", "CAPTURE_INTERRUPTED", "RECOVERED_WAV") &&
            !state.status.startsWith("FAILED")) return
        val captured = state.directory?.let { File(it, "capture.wav") } ?: return
        val finalized = File(captured.parentFile, "capture-finalized.txt").isFile || File(captured.parentFile, "recovered.txt").isFile
        if (!finalized) return
        if (state.audioMs > 20 * 60 * 1000) {
            Text("Длинная запись сохранена. Полная обработка сохранит текст без сквозных меток говорящих.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        OutlinedButton(onClick = {
            startActivity(Intent(this, MainActivity::class.java).setAction("ru.neurostenographer.REALTIME_BATCH")
                .setData(android.net.Uri.fromFile(captured)).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP))
            finish()
        }, modifier = Modifier.fillMaxWidth()) {
            Text(if (refineOverlap) "Уточнить перекрытия" else "Распознать сохранённую запись как файл")
        }
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
