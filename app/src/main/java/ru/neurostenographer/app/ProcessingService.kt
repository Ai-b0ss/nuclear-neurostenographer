package ru.neurostenographer.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

/** Owns only foreground/CPU lifetime; audio and cancellation remain with the view model.
 * No restart after process death, no screen lock, no battery-optimisation exemption.
 */
class ProcessingService : Service() {
    private val handler = Handler(Looper.getMainLooper())
    private val observed = mutableSetOf<Long>()
    private var lastStartId = 0
    private var wake: PowerManager.WakeLock? = null
    private val timeout = Runnable { cancelObserved(); stopSelf() }
    private val checkOwners = object : Runnable {
        override fun run() {
            val empty = synchronized(owners) { owners.isEmpty() }
            if (empty && stopSelfResult(lastStartId)) return
            handler.postDelayed(this, 500)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        lastStartId = startId
        synchronized(owners) { observed.addAll(owners.keys) }
        try {
            if (wake == null) {
                val manager = getSystemService(NotificationManager::class.java)
                manager.createNotificationChannel(NotificationChannel(CHANNEL,
                    "Обработка аудио", NotificationManager.IMPORTANCE_LOW))
                val open = PendingIntent.getActivity(this, ID,
                    Intent(this, MainActivity::class.java).addFlags(
                        Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP),
                    PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
                val stop = PendingIntent.getService(this, ID,
                    Intent(this, ProcessingService::class.java).setAction(STOP),
                    PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
                val notification = Notification.Builder(this, CHANNEL)
                    .setSmallIcon(android.R.drawable.ic_btn_speak_now)
                    .setContentTitle("Идёт расшифровка")
                    .setContentText("Можно выключить экран. Звук остаётся на устройстве.")
                    .setContentIntent(open).setOngoing(true)
                    .addAction(Notification.Action.Builder(null, "Остановить", stop).build())
                    .build()
                // Even a release racing with startup must first satisfy the FGS deadline.
                ServiceCompat.startForeground(this, ID, notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
                wake = getSystemService(PowerManager::class.java).newWakeLock(
                    PowerManager.PARTIAL_WAKE_LOCK, "$packageName:transcription").apply {
                    setReferenceCounted(false)
                    acquire(MAX_MILLIS)
                }
                instance = this
                mutableActive.value = true
                handler.postDelayed(timeout, MAX_MILLIS)
            }
            if (intent?.action == STOP) {
                cancelObserved()
                stopSelf()
            } else {
                handler.removeCallbacks(checkOwners)
                handler.post(checkOwners)
            }
        } catch (_: Exception) {
            // A foreground/lock failure must not leave background native work unowned.
            cancelObserved()
            stopSelf()
        }
        return START_NOT_STICKY
    }

    override fun onTimeout(startId: Int, fgsType: Int) {
        cancelObserved()
        stopSelf()
    }

    private fun cancelObserved() {
        val callbacks = synchronized(owners) { observed.mapNotNull { owners.remove(it) } }
        callbacks.forEach { runCatching { it() } }
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        wake?.let { if (it.isHeld) it.release() }
        wake = null
        if (instance === this) {
            instance = null
            mutableActive.value = false
        }
        // Do not cancel a new start that has not yet been delivered to this instance.
        cancelObserved()
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }

    companion object {
        private const val CHANNEL = "processing"
        private const val ID = 32
        internal const val STOP = "ru.neurostenographer.app.STOP_PROCESSING"
        private const val MAX_MILLIS = 6 * 60 * 60 * 1000L
        private val ids = AtomicLong()
        private val owners = mutableMapOf<Long, () -> Unit>()
        @Volatile private var instance: ProcessingService? = null
        private val mutableActive = MutableStateFlow(false)
        val active = mutableActive.asStateFlow()
        internal val wakeLockHeld: Boolean get() = instance?.wake?.isHeld == true

        fun acquire(context: Context, onCancel: () -> Unit): AutoCloseable {
            val id = ids.incrementAndGet()
            synchronized(owners) { owners[id] = onCancel }
            try {
                // Always deliver a startId, including when a previous lease is stopping.
                ContextCompat.startForegroundService(context,
                    Intent(context, ProcessingService::class.java))
            } catch (_: Exception) {
                synchronized(owners) { owners.remove(id) }
                // Foreground UI retains its screen-awake fallback if Android denies FGS.
            }
            val closed = AtomicBoolean()
            return AutoCloseable {
                if (closed.compareAndSet(false, true)) synchronized(owners) { owners.remove(id) }
            }
        }
    }
}
