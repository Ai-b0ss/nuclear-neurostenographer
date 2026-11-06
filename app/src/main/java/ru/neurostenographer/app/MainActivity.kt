package ru.neurostenographer.app

import android.Manifest
import android.content.Intent
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
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import kotlinx.coroutines.delay
import ru.neurostenographer.core.PcmWav
import ru.neurostenographer.core.TermEdit
import ru.neurostenographer.core.TranscriptExport
import ru.neurostenographer.core.TranscriptSegment
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : ComponentActivity() {
    private val model: TranscriptionViewModel by viewModels()
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { StenoTheme { ApplicationScreen() } }
        selectRealtimeFallback(intent)
    }
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        selectRealtimeFallback(intent)
    }
    override fun onResume() {
        super.onResume()
        if (BuildConfig.REALTIME) model.refreshHistory()
    }
    private fun selectRealtimeFallback(intent: Intent?) {
        if (!BuildConfig.REALTIME || intent?.action != "ru.neurostenographer.REALTIME_BATCH") return
        val uri = intent.data ?: return
        if (uri.scheme != "file") return
        val file = java.io.File(uri.path ?: return).canonicalFile
        val root = java.io.File(filesDir, "realtime").canonicalFile
        // Explicit own-file action only; exported activity cannot select another app's files.
        if (file.name == "capture.wav" && file.parentFile?.parentFile == root &&
            (java.io.File(file.parentFile, "capture-finalized.txt").isFile || java.io.File(file.parentFile, "recovered.txt").isFile)) {
            model.select(android.net.Uri.fromFile(file))
        }
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
        val importAudio = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            if (uri == null) notice = "Выбор файла отменён."
            else {
                notice = ""
                model.select(uri)
            }
        }
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
                onRename = { model.rename(current.id, it) },
                onRenameSpeaker = { speaker, name -> model.renameSpeaker(current.id, speaker, name) },
                suggestions = remember(current, state.userTerms) { model.termSuggestions(current) },
                onResolveTerms = { accepted, declined -> model.resolveTerms(current.id, accepted, declined) },
                onRevertTerms = { model.revertTerms(current.id) }, onAddTerm = model::addUserTerm,
                onShare = {
                    model.shareText()?.let { text ->
                        val send = Intent(Intent.ACTION_SEND).setType("text/plain")
                            .putExtra(Intent.EXTRA_SUBJECT, current.title).putExtra(Intent.EXTRA_TEXT, text)
                        runCatching { startActivity(Intent.createChooser(send, "Поделиться стенограммой")) }
                    }
                }, onExport = { format ->
                    model.prepareExport(format)
                    val name = TranscriptExport.fileBase(current.title)
                    when (format) {
                        "json" -> exportJson.launch("$name.json")
                        "srt" -> exportSrt.launch("$name.srt")
                        else -> exportTxt.launch("$name.txt")
                    }
                })
        } else {
            HomeScreen(state, recording, notice, onRecord = record,
                onImport = {
                    notice = "Выберите аудиофайл в системном окне."
                    importAudio.launch(arrayOf("audio/*", "application/ogg", "application/octet-stream"))
                },
                onTranscribe = model::transcribe, onCancel = model::cancel, onOpen = model::open,
                onRealtime = if (BuildConfig.REALTIME) ({
                    startActivity(Intent().setClassName(this@MainActivity, "ru.neurostenographer.app.RealtimeActivity"))
                }) else null)
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
private fun speakerName(id: String?, names: Map<String, String> = emptyMap()) = TranscriptExport.displaySpeaker(id, names)

private fun clock(ms: Long): String {
    val s = ms / 1000
    return if (s >= 3600) "%d:%02d:%02d".format(s / 3600, s / 60 % 60, s % 60) else "%02d:%02d".format(s / 60, s % 60)
}
private fun date(ms: Long) = SimpleDateFormat("d MMMM, HH:mm", Locale("ru")).format(Date(ms))

// ---------- Home ----------

@Composable
private fun HomeScreen(state: ScreenState, recording: Boolean, notice: String, onRecord: () -> Unit, onImport: () -> Unit,
                       onTranscribe: () -> Unit, onCancel: () -> Unit, onOpen: (String) -> Unit,
                       onRealtime: (() -> Unit)? = null) {
    val elapsed by produceState(0L, recording) {
        if (!recording) value = 0L else {
            val started = SystemClock.elapsedRealtime()
            while (true) { value = SystemClock.elapsedRealtime() - started; delay(250) }
        }
    }
    val listState = rememberLazyListState()
    // Imported file card is near the top; bring it into view even if the user
    // was scrolling old transcripts before opening the system file picker.
    LaunchedEffect(state.source, state.sourceDurationMs) {
        if (state.source != null) listState.animateScrollToItem(0)
    }
    Scaffold(containerColor = MaterialTheme.colorScheme.background) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), state = listState, contentPadding = PaddingValues(20.dp),
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
            } else if (state.message.isNotBlank()) item {
                Text(state.message, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
            }
            if (onRealtime != null) item {
                OutlinedButton(onClick = onRealtime, enabled = !state.busy && !recording && state.modelReady,
                    modifier = Modifier.fillMaxWidth()) { Text("Realtime · эксперимент") }
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
                             onRename: (String) -> Unit, onRenameSpeaker: (String, String) -> Unit,
                             suggestions: List<TermEdit>, onResolveTerms: (List<TermEdit>, List<TermEdit>) -> Unit,
                             onRevertTerms: () -> Unit, onAddTerm: (String, String) -> Unit,
                             onShare: () -> Unit, onExport: (String) -> Unit) {
    var renaming by remember { mutableStateOf(false) }
    var confirmDelete by remember { mutableStateOf(false) }
    var naming by remember { mutableStateOf<String?>(null) }
    var reviewingTerms by remember { mutableStateOf(false) }
    var query by remember(item.id) { mutableStateOf("") }
    val names = item.speakerNames
    val segments = item.shownSegments
    val editedIndexes = item.termEdits.map { it.segment }.toSet()
    val counts = segments.groupingBy { it.speakerId }.eachCount()
    val needle = query.trim()
    val shown = segments.withIndex().filter { (_, it) -> needle.isEmpty() ||
        it.text.contains(needle, ignoreCase = true) || speakerName(it.speakerId, names).contains(needle, ignoreCase = true)
    }
    val hits = if (needle.isEmpty()) 0 else shown.sumOf { (_, it) -> occurrences(it.text, needle) + occurrences(speakerName(it.speakerId, names), needle) }
    Scaffold(containerColor = MaterialTheme.colorScheme.background, topBar = {
        TopAppBar(title = { Text(item.title, maxLines = 1, overflow = TextOverflow.Ellipsis) },
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Назад") } },
            actions = {
                IconButton(onClick = onShare, enabled = !state.busy) { Icon(Icons.Filled.Share, "Поделиться") }
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
                        Surface(shape = RoundedCornerShape(50), color = speakerColor(id).copy(alpha = 0.14f),
                            modifier = Modifier.clip(RoundedCornerShape(50))
                                .clickable(enabled = id != null && !state.busy) { naming = id }) {
                            Row(Modifier.padding(horizontal = 10.dp, vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
                                Box(Modifier.size(10.dp).clip(CircleShape).background(speakerColor(id)))
                                Spacer(Modifier.width(6.dp))
                                Text("${speakerName(id, names)} · $n", style = MaterialTheme.typography.labelMedium)
                                if (id != null) {
                                    Spacer(Modifier.width(4.dp))
                                    Icon(Icons.Filled.Edit, null, Modifier.size(12.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
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
            if (segments.isNotEmpty()) item {
                val label = when {
                    suggestions.isNotEmpty() -> "Исправить термины (${suggestions.size})"
                    item.termEdits.isNotEmpty() -> "Термины исправлены (${item.termEdits.size})"
                    else -> "Словарь терминов"
                }
                FilledTonalButton(onClick = { reviewingTerms = true }, enabled = !state.busy,
                    contentPadding = PaddingValues(horizontal = 14.dp)) { Text(label) }
            }
            if (segments.isNotEmpty()) item {
                OutlinedTextField(query, { query = it }, Modifier.fillMaxWidth(), singleLine = true,
                    placeholder = { Text("Поиск по тексту и именам") },
                    leadingIcon = { Icon(Icons.Filled.Search, null) },
                    trailingIcon = if (query.isEmpty()) null else ({
                        IconButton(onClick = { query = "" }) { Icon(Icons.Filled.Close, "Очистить поиск") }
                    }),
                    supportingText = if (needle.isEmpty()) null else ({
                        Text(if (shown.isEmpty()) "Совпадений нет" else "Совпадений: $hits · реплик: ${shown.size} из ${segments.size}")
                    }), shape = RoundedCornerShape(14.dp))
            }
            if (segments.isEmpty()) item { Text("Речь не распознана.", color = MaterialTheme.colorScheme.onSurfaceVariant) }
            items(shown) { (index, it) -> Reply(it, names, needle, edited = index in editedIndexes,
                onSpeaker = { id -> if (!state.busy) naming = id }) }
            item {
                Spacer(Modifier.height(8.dp))
                Text("Время — границы реплик, не отдельных слов. Нажмите на говорящего, чтобы указать имя.",
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
    naming?.let { speaker ->
        var text by remember(speaker) { mutableStateOf(names[speaker].orEmpty()) }
        AlertDialog(onDismissRequest = { naming = null }, title = { Text("Имя говорящего") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Вместо «${speakerName(speaker)}» в стенограмме и экспорте TXT/SRT.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    OutlinedTextField(text, { text = it.take(40) }, singleLine = true, placeholder = { Text("Например, Иван") })
                }
            },
            confirmButton = { TextButton(onClick = { onRenameSpeaker(speaker, text); naming = null }) { Text("Сохранить") } },
            dismissButton = {
                Row {
                    if (names.containsKey(speaker)) TextButton(onClick = { onRenameSpeaker(speaker, ""); naming = null }) { Text("Сбросить") }
                    TextButton(onClick = { naming = null }) { Text("Отмена") }
                }
            })
    }
    if (reviewingTerms) TermsDialog(item, suggestions, onDismiss = { reviewingTerms = false },
        onApply = { a, d -> onResolveTerms(a, d); reviewingTerms = false },
        onRevert = { onRevertTerms(); reviewingTerms = false }, onAddTerm = onAddTerm)
    if (confirmDelete) AlertDialog(onDismissRequest = { confirmDelete = false }, title = { Text("Удалить стенограмму?") },
        text = { Text("Она будет удалена с телефона. Экспортированные файлы останутся.") },
        confirmButton = { TextButton(onClick = { confirmDelete = false; onDelete() }) { Text("Удалить") } },
        dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Отмена") } })
}

private fun occurrences(text: String, needle: String): Int {
    var count = 0
    var at = text.indexOf(needle, ignoreCase = true)
    while (at >= 0) { count++; at = text.indexOf(needle, at + needle.length, ignoreCase = true) }
    return count
}

private fun highlighted(text: String, needle: String, mark: Color): AnnotatedString = buildAnnotatedString {
    append(text)
    if (needle.isEmpty()) return@buildAnnotatedString
    var at = text.indexOf(needle, ignoreCase = true)
    while (at >= 0) {
        addStyle(SpanStyle(background = mark, fontWeight = FontWeight.SemiBold), at, at + needle.length)
        at = text.indexOf(needle, at + needle.length, ignoreCase = true)
    }
}

@Composable
private fun Reply(segment: TranscriptSegment, names: Map<String, String>, needle: String, edited: Boolean = false,
                  onSpeaker: (String) -> Unit) {
    val color = speakerColor(segment.speakerId)
    Row(Modifier.fillMaxWidth()) {
        Box(Modifier.width(4.dp).heightIn(min = 40.dp).clip(RoundedCornerShape(2.dp)).background(color))
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                val id = segment.speakerId
                Text(highlighted(speakerName(id, names), needle, Color(0xFFFFD54F).copy(alpha = 0.55f)), color = color, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold,
                    modifier = if (id != null) Modifier.clip(RoundedCornerShape(4.dp)).clickable { onSpeaker(id) } else Modifier)
                Spacer(Modifier.width(8.dp))
                Text("${clock(segment.startMs)}–${clock(segment.endMs)}", style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (segment.overlappingSpeech) {
                    Spacer(Modifier.width(8.dp))
                    Text("перекрытие", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                if (edited) {
                    Spacer(Modifier.width(8.dp))
                    Text("правка", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                }
            }
            Text(highlighted(segment.text, needle, Color(0xFFFFD54F).copy(alpha = 0.55f)), style = MaterialTheme.typography.bodyLarge)
        }
    }
}

/** «было → стало» review of the term dictionary proposals; the raw ASR text is kept and can be restored. */
@Composable
private fun TermsDialog(item: SavedTranscript, suggestions: List<TermEdit>, onDismiss: () -> Unit,
                        onApply: (List<TermEdit>, List<TermEdit>) -> Unit, onRevert: () -> Unit, onAddTerm: (String, String) -> Unit) {
    val checked = remember(suggestions) { mutableStateMapOf<TermEdit, Boolean>().apply { suggestions.forEach { put(it, !it.ambiguous) } } }
    var heard by remember { mutableStateOf("") }
    var written by remember { mutableStateOf("") }
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Написание терминов") },
        text = {
            Column(Modifier.heightIn(max = 460.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(if (suggestions.isEmpty()) "Новых предложений нет. Исходный текст распознавания сохраняется всегда."
                    else "Отметьте, что исправить. Исходный текст распознавания сохраняется, правки можно отменить.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                suggestions.forEach { e ->
                    val text = item.document.segments[e.segment].text
                    val context = "…" + text.substring(maxOf(0, e.start - 24), minOf(text.length, e.end + 24)) + "…"
                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth().clickable { checked[e] = checked[e] != true }) {
                        Checkbox(checked = checked[e] == true, onCheckedChange = { checked[e] = it })
                        Column(Modifier.weight(1f)) {
                            Text("«${e.original}» → ${e.replacement}", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
                            Text(context, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 2, overflow = TextOverflow.Ellipsis)
                            if (e.ambiguous) Text("может быть обычным словом", style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.error)
                        }
                    }
                }
                if (item.termEdits.isNotEmpty()) TextButton(onClick = onRevert) { Text("Вернуть исходный текст (правок: ${item.termEdits.size})") }
                HorizontalDivider()
                Text("Свой термин", style = MaterialTheme.typography.labelLarge)
                OutlinedTextField(heard, { heard = it.take(60) }, singleLine = true, label = { Text("Как распознано") },
                    placeholder = { Text("шерпа онникс") })
                OutlinedTextField(written, { written = it.take(60) }, singleLine = true, label = { Text("Как писать") },
                    placeholder = { Text("sherpa-onnx") })
                TextButton(onClick = { onAddTerm(heard, written); heard = ""; written = "" },
                    enabled = heard.isNotBlank() && written.isNotBlank() && !heard.contains('*')) { Text("Добавить в словарь") }
            }
        },
        confirmButton = {
            TextButton(onClick = { onApply(suggestions.filter { checked[it] == true }, suggestions.filter { checked[it] != true }) },
                enabled = suggestions.isNotEmpty()) { Text("Применить") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Закрыть") } })
}