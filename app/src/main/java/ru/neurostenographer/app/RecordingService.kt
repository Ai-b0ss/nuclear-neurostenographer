package ru.neurostenographer.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat

/** Keeps the process and microphone access alive while a recording runs in the background.
 * It owns no audio: the view model records, this service only holds the foreground state.
 */
class RecordingService : Service() {
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL, "Запись разговора",
            NotificationManager.IMPORTANCE_LOW))
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val notification = Notification.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle("Идёт запись")
            .setContentText("Звук остаётся на устройстве. Нажмите, чтобы остановить запись.")
            .setContentIntent(open).setOngoing(true).build()
        try {
            ServiceCompat.startForeground(this, ID, notification,
                if (Build.VERSION.SDK_INT >= 30) ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE else 0)
            active = true
        } catch (e: Exception) {
            active = false
        }
        starting = false
        // Stopping before startForeground() crashes the process, so a stop that raced
        // with the start is carried out here, after the foreground state was entered.
        if (!active || stopRequested) {
            stopRequested = false
            ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
            active = false
            stopSelf()
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        active = false
        super.onDestroy()
    }

    companion object {
        private const val CHANNEL = "recording"
        private const val ID = 1
        /** True only while the system accepted the foreground state. */
        @Volatile var active = false
            private set
        @Volatile private var starting = false
        @Volatile private var stopRequested = false

        fun start(context: Context) {
            stopRequested = false
            starting = true
            runCatching { ContextCompat.startForegroundService(context, Intent(context, RecordingService::class.java)) }
                .onFailure { starting = false }
        }

        fun stop(context: Context) {
            if (starting) { stopRequested = true; return }
            runCatching { context.stopService(Intent(context, RecordingService::class.java)) }
            active = false
        }
    }
}
