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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import java.io.File

class RealtimeActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Recover only feature-owned unfinished WAV headers; existing history is untouched.
        RealtimeService.recover(filesDir)
        if (RealtimeService.view.value.status == "IDLE") {
            File(filesDir, "realtime").listFiles().orEmpty().filter { it.isDirectory && it.name.matches(Regex("\\d+")) }
                .maxByOrNull { it.name }?.let { dir ->
                    val audio = File(dir, "capture.wav")
                    if (audio.length() >= 3244) RealtimeService.view.value = RealtimeView("RECOVERED_WAV", directory = dir.absolutePath,
                        audioMs = (audio.length() - 44) / 32)
                }
        }
        setContent { MaterialTheme {
            val state by RealtimeService.view.collectAsState()
            val start = {
                runCatching { ContextCompat.startForegroundService(this, Intent(this, RealtimeService::class.java)) }
                    .onFailure { RealtimeService.view.value = RealtimeView("Не удалось начать запись. Вернитесь в приложение и повторите.") }
                Unit
            }
            val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
                if (ok && lifecycle.currentState.isAtLeast(androidx.lifecycle.Lifecycle.State.STARTED)) start()
                else RealtimeService.view.value = RealtimeView(if (ok) "Вернитесь в приложение и нажмите «Начать»." else "Разрешение микрофона отклонено.")
            }
            var exportText by remember { mutableStateOf("") }
            val export = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri ->
                if (uri != null) contentResolver.openOutputStream(uri, "wt")?.use { it.write(exportText.toByteArray()) }
            }
            Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Realtime · эксперимент", style = MaterialTheme.typography.headlineSmall)
                Text("WAV сохраняется отдельно. Текст появляется после фразы; метки говорящих предварительные. После остановки выполняется полное уточнение говорящих. Перекрытия и неизвестные сохраняются.")
                Text("${state.status} · ${state.audioMs / 1000} с")
                val running = state.status in listOf("LOADING", "RUNNING", "FINALIZING", "CAPTURE_ONLY")
                Button(enabled = !running, onClick = {
                    if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) start()
                    else permission.launch(Manifest.permission.RECORD_AUDIO)
                }) { Text("Начать realtime запись") }
                Button(enabled = running, onClick = { startService(Intent(this@RealtimeActivity, RealtimeService::class.java).setAction("STOP")) }) { Text("Остановить и завершить") }
                Button(enabled = running, onClick = { startService(Intent(this@RealtimeActivity, RealtimeService::class.java).setAction("CANCEL")) }) { Text("Отменить обработку, сохранить WAV") }
                Button(enabled = state.document != null, onClick = { exportText = state.document!!.export("json"); export.launch("realtime.json") }) { Text("Экспорт JSON") }
                TextButton(onClick = { finish() }) { Text("К пакетному режиму и истории") }
                val captured = state.directory?.let { File(it, "capture.wav") }
                val finalized = captured != null && (File(captured.parentFile, "capture-finalized.txt").isFile || File(captured.parentFile, "recovered.txt").isFile)
                Button(enabled = !running && finalized && state.audioMs <= 20 * 60 * 1000, onClick = {
                    startActivity(Intent(this@RealtimeActivity, MainActivity::class.java).setAction("ru.neurostenographer.REALTIME_BATCH")
                        .setData(android.net.Uri.fromFile(captured)).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP))
                    finish()
                }) { Text("Сохранённый WAV → пакетное распознавание") }
                if (state.audioMs > 20 * 60 * 1000) Text("Пакетный режим ограничен 20 минутами; длинный WAV сохранён для отдельной обработки.")
                Text("После прерывания сохранённый WAV доступен для пакетного повтора. Автоматического продолжения после гибели процесса нет.")
                state.document?.segments?.forEach { Text("${it.startMs / 1000.0} · ${it.speakerId ?: "Не определён"}${if (it.overlappingSpeech) " · перекрытие" else ""}\n${it.text}") }
            }
        } }
    }
}
