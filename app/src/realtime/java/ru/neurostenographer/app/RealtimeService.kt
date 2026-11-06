package ru.neurostenographer.app

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.ServiceCompat
import kotlinx.coroutines.flow.MutableStateFlow
import ru.neurostenographer.core.TranscriptDocument
import java.io.File

/** Owns the session independently of the Activity, including HOME, rotation and screen-off. */
class RealtimeService : Service() {
    private var capture: RealtimeCapture? = null
    private var journal: RealtimeJournal? = null
    private var inference: RealtimeSession? = null
    private var wake: PowerManager.WakeLock? = null
    override fun onBind(intent: Intent?): IBinder? = null
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val benchmark = intent?.getBooleanExtra("benchmarkHold", false) == true
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel("realtime", "Realtime запись", NotificationManager.IMPORTANCE_LOW))
        val open = PendingIntent.getActivity(this, 0, Intent(this, RealtimeActivity::class.java), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val notification = Notification.Builder(this, "realtime").setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle(if (benchmark) "Realtime: проверка синтетического аудио" else "Идёт realtime запись")
            .setContentText("Звук остаётся на устройстве").setContentIntent(open).setOngoing(true).build()
        try {
            ServiceCompat.startForeground(this, 31, notification, if (Build.VERSION.SDK_INT >= 30) ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE else 0)
        } catch (e: Exception) {
            view.value = RealtimeView("FAILED: foreground service unavailable")
            stopSelf(); return START_NOT_STICKY
        }
        foreground = true
        if (intent?.action == "STOP" || intent?.action == "CANCEL") {
            if (capture == null) { stopSelf(); return START_NOT_STICKY }
            capture?.requestStop()
            if (intent.action == "CANCEL") inference?.cancel()
            return START_NOT_STICKY
        }
        if (benchmark) {
            // Instrumentation replays only synthetic PCM; this holds the same foreground
            // lifetime as live recording, including on the locked HONOR. No microphone.
            if (wake == null) wake = (getSystemService(POWER_SERVICE) as PowerManager)
                .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "neurostenographer:realtime-benchmark")
                .also { it.acquire(125 * 60 * 1000L) }
            return START_NOT_STICKY
        }
        if (capture != null) return START_NOT_STICKY
        try {
            check(checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) { "Нет разрешения микрофона" }
            recover(this.filesDir)
            val dir = File(filesDir, "realtime/${System.currentTimeMillis()}").apply { mkdirs() }
            val input = RealtimeJournal(File(dir, "capture.wav")); journal = input
            val captureOnly = intent?.getBooleanExtra("captureOnly", false) == true
            val duration = intent?.getIntExtra("seconds", 3600)?.coerceIn(1, 3600) ?: 3600
            val session = if (captureOnly) null else RealtimeSession(this, input) { status, document ->
                view.value = RealtimeView(status, document, dir.absolutePath, input.samples / 16)
            }; inference = session
            val mic = RealtimeCapture(this, input, duration); capture = mic
            wake = (getSystemService(POWER_SERVICE) as PowerManager).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,
                "neurostenographer:realtime").also { it.acquire(125 * 60 * 1000L) }
            captureActive = true
            mic.start(); session?.start()
            view.value = RealtimeView(if (captureOnly) "CAPTURE_ONLY" else "LOADING", null, dir.absolutePath, 0)
            Thread {
                while (mic.isRunning) {
                    view.value = view.value.copy(audioMs = input.samples / 16)
                    if (session?.state == "FAILED") mic.requestStop()
                    Thread.sleep(250)
                }
                captureActive = false // writer has finished; recovery may inspect its WAV now
                if (session == null) {
                    val metrics = org.json.JSONObject().put("status", if (input.failure == null) "PASS" else "FAIL")
                        .put("scope", "PHYSICAL_FOREGROUND_CAPTURE_ONLY_NO_TRANSCRIPTION_NO_AUDIO_EXPORT")
                        .put("samples", input.samples).put("wav_bytes", input.file.length()).put("capture_failure", input.failure ?: org.json.JSONObject.NULL)
                        .put("max_read_gap_ms", mic.maxReadGapMs).put("hardware_frame_position", mic.hardwareFramePosition)
                        .put("hardware_timestamp_samples", mic.timestampSamples)
                    File(filesDir, "realtime-microphone-screenoff.json").writeText(metrics.toString(2))
                    view.value = view.value.copy(status = "CAPTURE_ONLY_COMPLETE")
                    input.close(); stopSelf(); return@Thread
                }
                session.join(65 * 60 * 1000L)
                if (!session.isRunning) { input.close(); stopSelf() }
                // A still-running native call retains journal ownership and foreground service.
                else {
                    session.cancel()
                    while (!session.join(1000)) Unit
                    input.close(); stopSelf()
                }
            }.start()
        } catch (e: Throwable) {
            view.value = RealtimeView("FAILED: ${e.message}")
            capture?.requestStop(); inference?.cancel()
            if (capture?.isRunning != true) {
                captureActive = false
                runCatching { journal?.finish() }; runCatching { journal?.close() }; stopSelf()
            }
        }
        return START_NOT_STICKY
    }
    override fun onDestroy() {
        foreground = false
        capture?.requestStop(); inference?.cancel()
        if (wake?.isHeld == true) wake?.release()
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }
    companion object {
        @Volatile var foreground = false
            private set
        @Volatile private var captureActive = false
        val view = MutableStateFlow(RealtimeView())
        fun recover(filesDir: File) {
            if (captureActive) return
            File(filesDir, "realtime").listFiles().orEmpty().filter { it.isDirectory }.forEach { dir ->
                val wav = File(dir, "capture.wav")
                // A completed writer has already persisted a valid header. Never reopen
                // its audio for repair or mislabel a clean recording as interrupted.
                if (wav.isFile && !File(dir, "capture-finalized.txt").exists() &&
                    !File(dir, "recovered.txt").exists()) {
                    runCatching { RealtimeJournal.recover(wav) }.onSuccess {
                        File(dir, "recovered.txt").writeText("Header checked/recovered from $it persisted samples; interrupted live inference is not resumed. Use batch recognition.\n")
                    }
                }
            }
        }
    }
}
data class RealtimeView(val status: String = "IDLE", val document: TranscriptDocument? = null,
    val directory: String? = null, val audioMs: Long = 0)
