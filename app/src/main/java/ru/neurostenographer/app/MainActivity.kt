package ru.neurostenographer.app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import kotlinx.coroutines.delay
import ru.neurostenographer.core.PcmWav
import ru.neurostenographer.core.TranscriptSegment
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : ComponentActivity() {
    private val model: TranscriptionViewModel by viewModels()
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { StenoTheme { ApplicationScreen() } }
    }
    override fun onStop() {
        // With the foreground service the recording survives; without it the system
        // may cut the microphone, so stop and keep what was recorded.
        if (!isChangingConfigurations && model.recording.value && !RecordingService.active) model.stopRecording()
        super.onStop()
    }

    @Composable
    private fun ApplicationScreen() {
        val state by model.state.collectAsState()
        val recording by model.recording.collectAsState()
        // A long recording must not stop because the screen timed out mid-processing.
        val view = LocalView.current
        DisposableEffect(view, state.busy, recording) {
            view.keepScreenOn = state.busy || recording
            onDispose { view.keepScreenOn = false }
        }
        var notice by remember { mutableStateOf("") }
        val importAudio = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let(model::select) }
        val exportTxt = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/plain"), model::finishExport)
        val exportJson = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json"), model::finishExport)
        val exportSrt = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/x-subrip"), model::finishExport)
        val notifications = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {}
        val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
            if (ok && Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(this@MainActivity,
                    Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                notifications.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
            if (ok && lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) model.startRecording()
            else notice = if (ok) "Вернитесь в приложение и нажмите «Записать»." else "Разрешение микрофона отклонено."
        }
        val record = {
            if (recording) model.stopRecording()
            else if (ContextCompat.checkSelfPermission(this@MainActivity, Manifest.permission.RECORD_AUDIO)
                == PackageManager.PERMISSION_GRANTED) model.startRecording()
            else permission.launch(Manifest.permission.RECORD_AUDIO)
        }
        val current = state.current
        if (current != null) {
            BackHandler { model.closeTranscript() }
            TranscriptScreen(current, state, onBack = model::closeTranscript, onDelete = { model.delete(current.id) },
                onRename = { model.rename(current.id, it) }, onExport = { format ->
                    model.prepareExport(format)
                    val name = current.title.substringBeforeLast('.').replace(Regex("[^\\p{L}\\p{N} _-]"), "_").ifBlank { "transcript" }
                    when (format) {
                        "json" -> exportJson.launch("$name.json")
                        "srt" -> exportSrt.launch("$name.srt")
                        else -> exportTxt.launch("$name.txt")
                    }
                })
        } else {
            HomeScreen(state, recording, notice, onRecord = record,
                onImport = { importAudio.launch(arrayOf("audio/*", "application/ogg", "application/octet-stream")) },
                onTranscribe = model::transcribe, onCancel = model::cancel, onOpen = model::open)
        }
    }
}

// ---------- Theme ----------

private val Indigo = Color(0xFF3F51D9)
private val LightColors = lightColorScheme(
    primary = Indigo, onPrimary = Color.White, primaryContainer = Color(0xFFE0E4FF), onPrimaryContainer = Color(0xFF0F1A6B),
    secondary = Color(0xFF5B5F72), background = Color(0xFFF7F7FB), surface = Color.White,
    surfaceVariant = Color(0xFFEEEFF6), onSurfaceVariant = Color(0xFF55586A), error = Color(0xFFD32F2F),
)
private val DarkColors = darkColorScheme(
    primary = Color(0xFFB9C3FF), onPrimary = Color(0xFF0F1A6B), primaryContainer = Color(0xFF2A3596), onPrimaryContainer = Color(0xFFE0E4FF),
    background = Color(0xFF111218), surface = Color(0xFF1A1B22), surfaceVariant = Color(0xFF262833),
    onSurfaceVariant = Color(0xFFB8BACB), error = Color(0xFFFF6B6B),
)

@Composable
private fun StenoTheme(content: @Composable () -> Unit) =
    MaterialTheme(colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors, content = content)

private val SpeakerColors = listOf(Color(0xFF3F51D9), Color(0xFFE0631C), Color(0xFF0E9F6E), Color(0xFFB0329E),
    Color(0xFF0B8DB5), Color(0xFFB8860B), Color(0xFF7A4DD8), Color(0xFFC0392B))

private fun speakerIndex(id: String?) = id?.substringAfterLast(' ')?.toIntOrNull()
private fun speakerColor(id: String?) = speakerIndex(id)?.let { SpeakerColors[(it - 1).mod(SpeakerColors.size)] } ?: Color(0xFF8A8D9C)
private fun speakerName(id: String?) = speakerIndex(id)?.let { "Говорящий $it" } ?: "Не определён"

private fun clock(ms: Long): String {
    val s = ms / 1000
    return if (s >= 3600) "%d:%02d:%02d".format(s / 3600, s / 60 % 60, s % 60) else "%02d:%02d".format(s / 60, s % 60)
}
private fun date(ms: Long) = SimpleDateFormat("d MMMM, HH:mm", Locale("ru")).format(Date(ms))

// ---------- Home ----------

@Composable
private fun HomeScreen(state: ScreenState, recording: Boolean, notice: String, onRecord: () -> Unit, onImport: () -> Unit,
                       onTranscribe: () -> Unit, onCancel: () -> Unit, onOpen: (String) -> Unit) {
    val elapsed by produceState(0L, recording) {
        if (!recording) value = 0L else {
            val started = SystemClock.elapsedRealtime()
            while (true) { value = SystemClock.elapsedRealtime() - started; delay(250) }
        }
    }
    Scaffold(containerColor = MaterialTheme.colorScheme.background) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)) {
            item {
                Column {
                    Text("Нейростенограф", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(6.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Pill("Без интернета"); Pill("Говорящие и время")
                    }
                }
            }
            if (recording) item {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
                    Column(Modifier.fillMaxWidth().padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(Modifier.size(12.dp).clip(CircleShape).background(MaterialTheme.colorScheme.error))
                            Spacer(Modifier.width(8.dp))
                            Text("Идёт запись", style = MaterialTheme.typography.titleMedium)
                        }
                        Text(clock(elapsed), fontSize = 44.sp, fontWeight = FontWeight.Light)
                        Text("Максимум ${PcmWav.MAX_LABEL}. " + if (RecordingService.active) "Можно свернуть приложение." else "Не сворачивайте приложение.",
                            style = MaterialTheme.typography.bodySmall)
                        Spacer(Modifier.height(12.dp))
                        Button(onClick = onRecord, enabled = !state.busy, colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)) {
                            Text("Остановить запись")
                        }
                    }
                }
            } else item {
                Row(Modifier.height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    BigAction("Записать", "разговор с микрофона", Modifier.weight(1f).fillMaxHeight(), enabled = !state.busy && state.modelReady, primary = true, onClick = onRecord)
                    BigAction("Открыть аудиофайл", "WAV, MP3, M4A… до 20 мин", Modifier.weight(1f).fillMaxHeight(), enabled = !state.busy && state.modelReady, onClick = onImport)
                }
            }
            if (state.busy) item {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)) {
                    Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text(state.message, style = MaterialTheme.typography.bodyMedium)
                        val p = state.progress
                        if (p != null) LinearProgressIndicator(progress = { p }, Modifier.fillMaxWidth())
                        else LinearProgressIndicator(Modifier.fillMaxWidth())
                        TextButton(onClick = onCancel, modifier = Modifier.align(Alignment.End)) { Text("Отменить") }
                    }
                }
            } else if (state.message.isNotBlank() && (state.source == null || !state.modelReady)) item {
                Text(state.message, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
            }
            if (notice.isNotEmpty()) item { Text(notice, color = MaterialTheme.colorScheme.error) }
            if (state.source != null && !recording && !state.busy) item {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface), elevation = CardDefaults.cardElevation(1.dp)) {
                    Column(Modifier.fillMaxWidth().padding(16.dp)) {
                        Text("Аудио готово", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                        Text(state.sourceName ?: "Аудио", style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        state.sourceDurationMs?.let { Text("Длительность ${clock(it)}", style = MaterialTheme.typography.bodySmall) }
                        Spacer(Modifier.height(12.dp))
                        Button(onClick = onTranscribe, enabled = state.modelReady, modifier = Modifier.fillMaxWidth().height(52.dp)) {
                            Text("Распознать", style = MaterialTheme.typography.titleMedium)
                        }
                    }
                }
            }
            item {
                Text("Стенограммы", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(top = 8.dp))
            }
            if (state.history.isEmpty()) item {
                Text("Здесь появятся готовые расшифровки. Они хранятся только на телефоне.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
            }
            items(state.history, key = { it.id }) { item ->
                Card(Modifier.fillMaxWidth().clickable(enabled = !state.busy) { onOpen(item.id) },
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface), elevation = CardDefaults.cardElevation(1.dp)) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(item.title, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text("${date(item.createdMs)} · ${clock(item.document.audioMs)} · говорящих: ${item.speakers.size}",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        item.document.segments.firstOrNull()?.let {
                            Text(it.text, style = MaterialTheme.typography.bodyMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun Pill(text: String) = Surface(shape = RoundedCornerShape(50), color = MaterialTheme.colorScheme.surfaceVariant) {
    Text(text, Modifier.padding(horizontal = 10.dp, vertical = 4.dp), style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable
private fun BigAction(title: String, subtitle: String, modifier: Modifier, enabled: Boolean, primary: Boolean = false, onClick: () -> Unit) {
    val colors = if (primary) CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primary, contentColor = MaterialTheme.colorScheme.onPrimary)
    else CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    Card(onClick = onClick, enabled = enabled, modifier = modifier.heightIn(min = 112.dp), colors = colors,
        elevation = CardDefaults.cardElevation(if (primary) 0.dp else 1.dp), shape = RoundedCornerShape(20.dp)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            if (primary) Box(Modifier.size(14.dp).clip(CircleShape).background(Color(0xFFFF5A5A)))
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(subtitle, style = MaterialTheme.typography.bodySmall)
        }
    }
}

// ---------- Transcript ----------

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
private fun TranscriptScreen(item: SavedTranscript, state: ScreenState, onBack: () -> Unit, onDelete: () -> Unit,
                             onRename: (String) -> Unit, onExport: (String) -> Unit) {
    var renaming by remember { mutableStateOf(false) }
    var confirmDelete by remember { mutableStateOf(false) }
    val segments = item.document.segments
    val counts = segments.groupingBy { it.speakerId }.eachCount()
    Scaffold(containerColor = MaterialTheme.colorScheme.background, topBar = {
        TopAppBar(title = { Text(item.title, maxLines = 1, overflow = TextOverflow.Ellipsis) },
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Назад") } },
            actions = {
                IconButton(onClick = { renaming = true }) { Icon(Icons.Filled.Edit, "Переименовать") }
                IconButton(onClick = { confirmDelete = true }) { Icon(Icons.Filled.Delete, "Удалить") }
            })
    }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)) {
            item {
                Text("${date(item.createdMs)} · ${clock(item.document.audioMs)} · реплик: ${segments.size}",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            item {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    counts.entries.sortedBy { speakerIndex(it.key) ?: Int.MAX_VALUE }.forEach { (id, n) ->
                        Surface(shape = RoundedCornerShape(50), color = speakerColor(id).copy(alpha = 0.14f)) {
                            Row(Modifier.padding(horizontal = 10.dp, vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
                                Box(Modifier.size(10.dp).clip(CircleShape).background(speakerColor(id)))
                                Spacer(Modifier.width(6.dp))
                                Text("${speakerName(id)} · $n", style = MaterialTheme.typography.labelMedium)
                            }
                        }
                    }
                }
            }
            item {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Экспорт", style = MaterialTheme.typography.labelLarge)
                    for (f in listOf("txt", "json", "srt")) OutlinedButton(onClick = { onExport(f) }, enabled = !state.busy,
                        contentPadding = PaddingValues(horizontal = 14.dp)) { Text(f.uppercase()) }
                }
            }
            if (segments.isEmpty()) item { Text("Речь не распознана.", color = MaterialTheme.colorScheme.onSurfaceVariant) }
            items(segments) { Reply(it) }
            item {
                Spacer(Modifier.height(8.dp))
                Text("Время — границы реплик, не отдельных слов. Говорящие пронумерованы моделью, имена не определяются.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (state.details.isNotBlank() && state.history.firstOrNull()?.id == item.id) Text(state.details,
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
    if (renaming) {
        var text by remember { mutableStateOf(item.title) }
        AlertDialog(onDismissRequest = { renaming = false }, title = { Text("Название") },
            text = { OutlinedTextField(text, { text = it }, singleLine = true) },
            confirmButton = { TextButton(onClick = { onRename(text); renaming = false }) { Text("Сохранить") } },
            dismissButton = { TextButton(onClick = { renaming = false }) { Text("Отмена") } })
    }
    if (confirmDelete) AlertDialog(onDismissRequest = { confirmDelete = false }, title = { Text("Удалить стенограмму?") },
        text = { Text("Она будет удалена с телефона. Экспортированные файлы останутся.") },
        confirmButton = { TextButton(onClick = { confirmDelete = false; onDelete() }) { Text("Удалить") } },
        dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Отмена") } })
}

@Composable
private fun Reply(segment: TranscriptSegment) {
    val color = speakerColor(segment.speakerId)
    Row(Modifier.fillMaxWidth()) {
        Box(Modifier.width(4.dp).heightIn(min = 40.dp).clip(RoundedCornerShape(2.dp)).background(color))
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(speakerName(segment.speakerId), color = color, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.width(8.dp))
                Text("${clock(segment.startMs)}–${clock(segment.endMs)}", style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (segment.overlappingSpeech) {
                    Spacer(Modifier.width(8.dp))
                    Text("перекрытие", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Text(segment.text, style = MaterialTheme.typography.bodyLarge)
        }
    }
}
