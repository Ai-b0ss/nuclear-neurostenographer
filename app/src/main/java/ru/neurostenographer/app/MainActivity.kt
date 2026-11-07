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
import androidx.compose.foundation.Canvas
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
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
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
        // Audio shared from a messenger or opened from a file manager is recognised without further taps.
        if (savedInstanceState == null) importSharedAudio(intent)
    }
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        selectRealtimeFallback(intent)
        importSharedAudio(intent)
    }
    @Suppress("DEPRECATION")
    private fun importSharedAudio(shared: Intent?) {
        val intent = shared ?: return
        val uri: android.net.Uri? = when (intent.action) {
            Intent.ACTION_SEND -> if (Build.VERSION.SDK_INT >= 33) intent.getParcelableExtra(Intent.EXTRA_STREAM, android.net.Uri::class.java)
                else intent.getParcelableExtra(Intent.EXTRA_STREAM)
            Intent.ACTION_VIEW -> intent.data
            else -> null
        }
        // Only content:// from other apps. file:// could point into this app's own private storage.
        if (uri == null || uri.scheme != "content") return
        intent.action = null // consumed: a later recreation must not import it again
        model.select(uri)
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
        val exportContest = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json"), model::finishExport)
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
        // Recognition starts by itself once audio is ready (recorded, picked or shared). One automatic
        // attempt per file: after a failure or cancel the user sees "Распознать" and decides.
        var autoStarted by rememberSaveable { mutableStateOf("") }
        LaunchedEffect(state.source, state.busy, recording, state.modelReady) {
            val source = state.source?.toString()
            if (source != null && !state.busy && !recording && state.modelReady && state.current == null && autoStarted != source) {
                autoStarted = source
                model.transcribe()
            }
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
                        "json-contest" -> exportContest.launch("$name.json")
                        "json" -> exportJson.launch("$name.full.json")
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
    secondary = Color(0xFF5B5F72), background = Color(0xFFF6F6FC), surface = Color.White,
    surfaceVariant = Color(0xFFECEDF6), onSurfaceVariant = Color(0xFF55586A), error = Color(0xFFD32F2F),
)
private val DarkColors = darkColorScheme(
    primary = Color(0xFFB9C3FF), onPrimary = Color(0xFF0F1A6B), primaryContainer = Color(0xFF2A3596), onPrimaryContainer = Color(0xFFE0E4FF),
    background = Color(0xFF101117), surface = Color(0xFF1A1B23), surfaceVariant = Color(0xFF272935),
    onSurfaceVariant = Color(0xFFB8BACB), error = Color(0xFFFF6B6B),
)

@Composable
internal fun StenoTheme(content: @Composable () -> Unit) =
    MaterialTheme(colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        shapes = Shapes(small = RoundedCornerShape(10.dp), medium = RoundedCornerShape(16.dp), large = RoundedCornerShape(24.dp)),
        content = content)

private val SpeakerColors = listOf(Color(0xFF3F51D9), Color(0xFFE0631C), Color(0xFF0E9F6E), Color(0xFFB0329E),
    Color(0xFF0B8DB5), Color(0xFFB8860B), Color(0xFF7A4DD8), Color(0xFFC0392B))

private fun speakerIndex(id: String?) = id?.substringAfterLast(' ')?.toIntOrNull()
private fun speakerColor(id: String?) = speakerIndex(id)?.let { SpeakerColors[(it - 1).mod(SpeakerColors.size)] } ?: Color(0xFF8A8D9C)
private fun speakerName(id: String?, names: Map<String, String> = emptyMap()) = TranscriptExport.displaySpeaker(id, names)
internal fun clock(ms: Long): String {
    val s = ms / 1000
    return if (s >= 3600) "%d:%02d:%02d".format(s / 3600, s / 60 % 60, s % 60) else "%02d:%02d".format(s / 60, s % 60)
}
private fun date(ms: Long) = SimpleDateFormat("d MMMM, HH:mm", Locale("ru")).format(Date(ms))

// ---------- Small pieces ----------

/** A microphone drawn from primitives, so the app needs no extended icon set. */
@Composable
private fun MicGlyph(color: Color, box: Dp) {
    Canvas(Modifier.size(box)) {
        val w = this.size.width
        val h = this.size.height
        val line = w * 0.08f
        drawRoundRect(color, topLeft = Offset(w * 0.36f, h * 0.08f), size = Size(w * 0.28f, h * 0.46f),
            cornerRadius = CornerRadius(w * 0.14f))
        drawArc(color, startAngle = 0f, sweepAngle = 180f, useCenter = false, topLeft = Offset(w * 0.24f, h * 0.26f),
            size = Size(w * 0.52f, h * 0.44f), style = Stroke(line, cap = StrokeCap.Round))
        drawLine(color, Offset(w * 0.5f, h * 0.70f), Offset(w * 0.5f, h * 0.88f), strokeWidth = line, cap = StrokeCap.Round)
        drawLine(color, Offset(w * 0.36f, h * 0.90f), Offset(w * 0.64f, h * 0.90f), strokeWidth = line, cap = StrokeCap.Round)
    }
}

/** Russian plural: 1 реплика, 2 реплики, 5 реплик. */
private fun plural(n: Int, one: String, few: String, many: String): String =
    "$n " + when {
        n % 100 in 11..14 -> many
        n % 10 == 1 -> one
        n % 10 in 2..4 -> few
        else -> many
    }

// ---------- Home ----------

@Composable
private fun HomeScreen(state: ScreenState, recording: Boolean, notice: String, onRecord: () -> Unit, onImport: () -> Unit,
                       onTranscribe: () -> Unit, onCancel: () -> Unit, onOpen: (String) -> Unit,
                       onRealtime: (() -> Unit)? = null) {
    val listState = rememberLazyListState()
    // An imported file is shown near the top; bring it into view even if the user
    // was scrolling old transcripts before opening the system file picker.
    LaunchedEffect(state.source, state.sourceDurationMs) {
        if (state.source != null) listState.animateScrollToItem(0)
    }
    Scaffold(containerColor = MaterialTheme.colorScheme.background) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), state = listState,
            contentPadding = PaddingValues(start = 24.dp, end = 24.dp, top = 24.dp, bottom = 32.dp)) {
            item {
                Column(Modifier.padding(bottom = 8.dp)) {
                    Text("Нейростенограф", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(4.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Filled.Lock, null, Modifier.size(14.dp), tint = MaterialTheme.colorScheme.primary)
                        Spacer(Modifier.width(5.dp))
                        Text("Без интернета", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            when {
                recording -> item { RecordingHero(enabled = !state.busy, onStop = onRecord) }
                state.busy -> item { Box(Modifier.padding(vertical = 8.dp)) { ProcessingCard(state, onCancel) } }
                else -> {
                    if (state.source != null) item { Box(Modifier.padding(vertical = 8.dp)) { PendingAudioCard(state, onTranscribe) } }
                    item { StartBlock(ready = state.modelReady, onRecord = onRecord, onImport = onImport, onRealtime = onRealtime) }
                }
            }
            if (!recording && !state.busy && state.message.isNotBlank() && state.message != TranscriptionViewModel.READY) item {
                Text(state.message, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(bottom = 12.dp))
            }
            if (notice.isNotEmpty()) item { Text(notice, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(bottom = 12.dp)) }
            item {
                Row(Modifier.padding(top = 20.dp, bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("Стенограммы", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                    if (state.history.isNotEmpty()) {
                        Spacer(Modifier.width(8.dp))
                        Text("${state.history.size}", style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            if (state.history.isEmpty()) item {
                Text("Здесь появятся готовые расшифровки. Они хранятся только на телефоне.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(vertical = 12.dp))
            }
            items(state.history, key = { it.id }) { item -> HistoryRow(item, enabled = !state.busy, onOpen = onOpen) }
        }
    }
}

/** No card: the record button is the page. Everything else is a quiet text action. */
@Composable
private fun StartBlock(ready: Boolean, onRecord: () -> Unit, onImport: () -> Unit, onRealtime: (() -> Unit)?) {
    val primary = MaterialTheme.colorScheme.primary
    Column(Modifier.fillMaxWidth().padding(top = 16.dp, bottom = 8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Column(Modifier.clip(RoundedCornerShape(28.dp)).clickable(enabled = ready, onClick = onRecord).padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally) {
            Box(Modifier.size(176.dp).alpha(if (ready) 1f else 0.4f), contentAlignment = Alignment.Center) {
                Box(Modifier.fillMaxSize().background(primary.copy(alpha = 0.10f), CircleShape))
                Box(Modifier.size(132.dp).background(primary, CircleShape), contentAlignment = Alignment.Center) {
                    MicGlyph(MaterialTheme.colorScheme.onPrimary, 56.dp)
                }
            }
            Spacer(Modifier.height(8.dp))
            Text("Записать", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
        }
        Spacer(Modifier.height(6.dp))
        Text("Остановите запись — расшифровка начнётся сама", style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
        Spacer(Modifier.height(20.dp))
        FilledTonalButton(onClick = onImport, enabled = ready, shape = RoundedCornerShape(50),
            contentPadding = PaddingValues(horizontal = 24.dp, vertical = 12.dp)) {
            Icon(Icons.Filled.Add, null, Modifier.size(20.dp))
            Spacer(Modifier.width(8.dp))
            Text("Открыть аудиофайл")
        }
        Spacer(Modifier.height(6.dp))
        Text("WAV, MP3, M4A · до 20 мин · или «Поделиться» из мессенджера", style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
        if (onRealtime != null) TextButton(onClick = onRealtime, enabled = ready, modifier = Modifier.padding(top = 4.dp)) {
            Text("Живая расшифровка")
        }
    }
}

@Composable
private fun RecordingHero(enabled: Boolean, onStop: () -> Unit) {
    // Own timer: only this card is redrawn while recording, not the whole list.
    val elapsed by produceState(0L) {
        val started = SystemClock.elapsedRealtime()
        while (true) { value = SystemClock.elapsedRealtime() - started; delay(100) }
    }
    val phase = (elapsed % 2000L) / 2000f
    val red = MaterialTheme.colorScheme.error
    Card(shape = RoundedCornerShape(28.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(3.dp)) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(10.dp).background(red, CircleShape))
                Spacer(Modifier.width(8.dp))
                Text("Идёт запись", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            }
            Box(Modifier.size(190.dp), contentAlignment = Alignment.Center) {
                Canvas(Modifier.fillMaxSize()) {
                    for (k in 0..1) {
                        val q = (phase + k * 0.5f) % 1f
                        drawCircle(red.copy(alpha = (1f - q) * 0.30f), radius = size.minDimension / 2 * (0.52f + 0.48f * q))
                    }
                }
                Box(Modifier.size(96.dp).background(red, CircleShape).clip(CircleShape)
                    .semantics { contentDescription = "Стоп" }.clickable(enabled = enabled, onClick = onStop),
                    contentAlignment = Alignment.Center) {
                    Box(Modifier.size(30.dp).background(Color.White, RoundedCornerShape(7.dp)))
                }
            }
            Text(clock(elapsed), fontSize = 48.sp, fontWeight = FontWeight.Light)
            Text("Максимум ${PcmWav.MAX_LABEL}. " + if (RecordingService.active) "Можно свернуть приложение." else "Не сворачивайте приложение.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(14.dp))
            Button(onClick = onStop, enabled = enabled, shape = RoundedCornerShape(16.dp),
                colors = ButtonDefaults.buttonColors(containerColor = red), modifier = Modifier.fillMaxWidth().height(52.dp)) {
                Text("Остановить запись")
            }
        }
    }
}

@Composable
private fun ProcessingCard(state: ScreenState, onCancel: () -> Unit) {
    val elapsed by produceState(0L) {
        val started = SystemClock.elapsedRealtime()
        while (true) { value = SystemClock.elapsedRealtime() - started; delay(1000) }
    }
    Card(shape = RoundedCornerShape(28.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer,
        contentColor = MaterialTheme.colorScheme.onPrimaryContainer)) {
        Column(Modifier.fillMaxWidth().padding(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(if (state.stage > 0) "Идёт расшифровка" else "Подождите", style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                Text(clock(elapsed), style = MaterialTheme.typography.labelLarge)
            }
            if (state.stage > 0) Steps(state.stage)
            Text(state.message, style = MaterialTheme.typography.bodyMedium)
            val p = state.progress
            if (p != null) LinearProgressIndicator(progress = { p }, Modifier.fillMaxWidth().clip(RoundedCornerShape(50)))
            else LinearProgressIndicator(Modifier.fillMaxWidth().clip(RoundedCornerShape(50)))
            Text("Экран не погаснет, пока идёт обработка. Всё считается на телефоне.", style = MaterialTheme.typography.bodySmall)
            TextButton(onClick = onCancel, modifier = Modifier.align(Alignment.End)) { Text("Отменить") }
        }
    }
}

@Composable
private fun Steps(stage: Int) {
    Row(Modifier.fillMaxWidth()) {
        listOf("Подготовка", "Говорящие", "Речь").forEachIndexed { index, label ->
            val n = index + 1
            val reached = stage >= n
            Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
                Box(Modifier.size(30.dp).background(if (reached) MaterialTheme.colorScheme.primary
                    else MaterialTheme.colorScheme.surface.copy(alpha = 0.6f), CircleShape), contentAlignment = Alignment.Center) {
                    if (stage > n) Icon(Icons.Filled.Check, null, Modifier.size(18.dp), tint = MaterialTheme.colorScheme.onPrimary)
                    else Text("$n", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.labelLarge,
                        color = if (reached) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Spacer(Modifier.height(4.dp))
                Text(label, style = MaterialTheme.typography.labelSmall,
                    fontWeight = if (stage == n) FontWeight.Bold else FontWeight.Normal)
            }
        }
    }
}

/** Audio that was not recognised (cancelled or failed): recognition normally starts by itself. */
@Composable
private fun PendingAudioCard(state: ScreenState, onTranscribe: () -> Unit) {
    Card(shape = RoundedCornerShape(24.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(1.dp)) {
        Column(Modifier.fillMaxWidth().padding(16.dp)) {
            Text("Аудио ждёт расшифровки", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
            Text(state.sourceName ?: "Аудио", style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            state.sourceDurationMs?.let { Text("Длительность ${clock(it)}", style = MaterialTheme.typography.bodySmall) }
            Spacer(Modifier.height(12.dp))
            Button(onClick = onTranscribe, enabled = state.modelReady, shape = RoundedCornerShape(16.dp),
                modifier = Modifier.fillMaxWidth().height(52.dp)) {
                Text("Распознать", style = MaterialTheme.typography.titleMedium)
            }
        }
    }
}

@Composable
private fun HistoryRow(item: SavedTranscript, enabled: Boolean, onOpen: (String) -> Unit) {
    Column(Modifier.fillMaxWidth()) {
        Column(Modifier.fillMaxWidth().clickable(enabled = enabled) { onOpen(item.id) }.padding(vertical = 14.dp)) {
            Text(item.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold, maxLines = 1,
                overflow = TextOverflow.Ellipsis)
            Spacer(Modifier.height(4.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                item.speakers.take(6).forEach { id ->
                    Box(Modifier.size(9.dp).background(speakerColor(id), CircleShape))
                    Spacer(Modifier.width(4.dp))
                }
                if (item.speakers.isNotEmpty()) Spacer(Modifier.width(4.dp))
                Text("${date(item.createdMs)} · ${clock(item.document.audioMs)}", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            item.document.segments.firstOrNull()?.let {
                Text(it.text, style = MaterialTheme.typography.bodyMedium, maxLines = 2, overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 6.dp))
            }
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f))
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
    var searching by remember(item.id) { mutableStateOf(false) }
    var menuOpen by remember { mutableStateOf(false) }
    var exportOpen by remember { mutableStateOf(false) }
    var query by remember(item.id) { mutableStateOf("") }
    val names = item.speakerNames
    val segments = item.shownSegments
    val editedIndexes = item.termEdits.map { it.segment }.toSet()
    val counts = segments.groupingBy { it.speakerId }.eachCount()
    val needle = query.trim()
    val shown = segments.withIndex().filter { (_, it) -> needle.isEmpty() ||
        it.text.contains(needle, ignoreCase = true) || TranscriptExport.segmentSpeaker(it, names).contains(needle, ignoreCase = true)
    }
    val hits = if (needle.isEmpty()) 0 else shown.sumOf { (_, it) -> occurrences(it.text, needle) + occurrences(TranscriptExport.segmentSpeaker(it, names), needle) }
    val termsLabel = when {
        suggestions.isNotEmpty() -> "Исправить термины (${suggestions.size})"
        item.termEdits.isNotEmpty() -> "Термины исправлены (${item.termEdits.size})"
        else -> "Словарь терминов"
    }
    Scaffold(containerColor = MaterialTheme.colorScheme.background, topBar = {
        TopAppBar(title = { Text(item.title, maxLines = 1, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.SemiBold) },
            colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Назад") } },
            actions = {
                if (segments.isNotEmpty()) IconButton(onClick = { searching = !searching; if (!searching) query = "" }) {
                    Icon(Icons.Filled.Search, "Поиск")
                }
                IconButton(onClick = onShare, enabled = !state.busy) { Icon(Icons.Filled.Share, "Поделиться") }
                Box {
                    IconButton(onClick = { menuOpen = true }) { Icon(Icons.Filled.MoreVert, "Ещё") }
                    DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                        DropdownMenuItem(text = { Text("Переименовать") }, onClick = { menuOpen = false; renaming = true })
                        DropdownMenuItem(text = { Text(termsLabel) }, enabled = segments.isNotEmpty() && !state.busy,
                            onClick = { menuOpen = false; reviewingTerms = true })
                        DropdownMenuItem(text = { Text("Удалить") }, onClick = { menuOpen = false; confirmDelete = true })
                    }
                }
            })
    }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(start = 20.dp, end = 20.dp, top = 4.dp, bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp)) {
            item {
                Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("${clock(item.document.audioMs)} · ${plural(segments.size, "реплика", "реплики", "реплик")}",
                                style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                            Text(date(item.createdMs), style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Box {
                            FilledTonalButton(onClick = { exportOpen = true }, enabled = !state.busy) { Text("Экспорт") }
                            DropdownMenu(expanded = exportOpen, onDismissRequest = { exportOpen = false }) {
                                for (f in listOf("json-contest", "txt", "json", "srt")) DropdownMenuItem(
                                    text = { Text(when (f) { "json-contest" -> "JSON"; "json" -> "JSON расш."; else -> f.uppercase() }) },
                                    onClick = { exportOpen = false; onExport(f) })
                            }
                        }
                    }
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        counts.entries.sortedBy { speakerIndex(it.key) ?: Int.MAX_VALUE }.forEach { (id, n) ->
                            Surface(shape = RoundedCornerShape(50), color = speakerColor(id).copy(alpha = 0.14f),
                                modifier = Modifier.clip(RoundedCornerShape(50))
                                    .clickable(enabled = id != null && !state.busy) { naming = id }) {
                                Row(Modifier.padding(horizontal = 12.dp, vertical = 7.dp), verticalAlignment = Alignment.CenterVertically) {
                                    Box(Modifier.size(10.dp).background(speakerColor(id), CircleShape))
                                    Spacer(Modifier.width(8.dp))
                                    Text("${speakerName(id, names)} · $n", style = MaterialTheme.typography.labelLarge)
                                    if (id != null) {
                                        Spacer(Modifier.width(6.dp))
                                        Icon(Icons.Filled.Edit, null, Modifier.size(12.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                }
                            }
                        }
                    }
                }
            }
            if (suggestions.isNotEmpty()) item {
                FilledTonalButton(onClick = { reviewingTerms = true }, enabled = !state.busy) { Text(termsLabel) }
            }
            if (segments.isNotEmpty() && (searching || query.isNotEmpty())) item {
                OutlinedTextField(query, { query = it }, Modifier.fillMaxWidth(), singleLine = true,
                    placeholder = { Text("Поиск по тексту и именам") },
                    leadingIcon = { Icon(Icons.Filled.Search, null) },
                    trailingIcon = if (query.isEmpty()) null else ({
                        IconButton(onClick = { query = "" }) { Icon(Icons.Filled.Close, "Очистить поиск") }
                    }),
                    supportingText = if (needle.isEmpty()) null else ({
                        Text(if (shown.isEmpty()) "Совпадений нет" else "Совпадений: $hits · реплик: ${shown.size} из ${segments.size}")
                    }), shape = RoundedCornerShape(50))
            }
            if (segments.isEmpty()) item { Text("Речь не распознана.", color = MaterialTheme.colorScheme.onSurfaceVariant) }
            items(shown) { (index, it) -> Reply(it, names, needle, edited = index in editedIndexes,
                onSpeaker = { id -> if (!state.busy) naming = id }) }
            item {
                Spacer(Modifier.height(4.dp))
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

/** One utterance: a thin speaker-coloured line, name and time on top, the text below. No boxes. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun Reply(segment: TranscriptSegment, names: Map<String, String>, needle: String, edited: Boolean = false,
                  onSpeaker: (String) -> Unit) {
    val color = speakerColor(segment.speakerId)
    val mark = Color(0xFFFFD54F).copy(alpha = 0.55f)
    val bar = with(androidx.compose.ui.platform.LocalDensity.current) { 3.dp.toPx() }
    Column(Modifier.fillMaxWidth().drawBehind {
        drawRoundRect(color, size = Size(bar, size.height), cornerRadius = CornerRadius(bar / 2))
    }.padding(start = 16.dp)) {
        FlowRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            val id = segment.speakerId
            Text(highlighted(TranscriptExport.segmentSpeaker(segment, names), needle, mark), color = color,
                style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold,
                modifier = if (id != null) Modifier.clip(RoundedCornerShape(4.dp)).clickable { onSpeaker(id) } else Modifier)
            Text("${clock(segment.startMs)}–${clock(segment.endMs)}", style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (segment.overlappingSpeech) Text("перекрытие", style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (edited) Text("правка", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
        }
        Spacer(Modifier.height(3.dp))
        Text(highlighted(segment.text, needle, mark), style = MaterialTheme.typography.bodyLarge)
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