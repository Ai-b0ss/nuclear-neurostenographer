package ru.neurostenographer.app

import android.app.Service
import android.app.ActivityManager
import android.app.Application
import android.content.Intent
import android.os.*
import java.io.DataInputStream
import java.io.File
import java.util.concurrent.Executors
import ru.neurostenographer.core.PcmAudio
import ru.neurostenographer.core.DiarizationReply

/** Private same-UID worker process. A JNI abort must not kill the UI/ASR process.
 * Samples travel through an app-private file, never through Binder's 1 MB buffer.
 */
class DiarizationService : Service() {
    private val worker = Executors.newSingleThreadExecutor()
    private var dedicatedProcess = false
    private var claimed = false
    override fun onCreate() {
        super.onCreate()
        val processName = if (Build.VERSION.SDK_INT >= 28) Application.getProcessName() else
            getSystemService(ActivityManager::class.java).runningAppProcesses
                ?.firstOrNull { it.pid == Process.myPid() }?.processName
        dedicatedProcess = processName == "$packageName:diarization"
    }
    private val messenger = Messenger(Handler(Looper.getMainLooper()) { request ->
        val reply = request.replyTo
        if (request.what != RUN || reply == null) return@Handler false
        if (claimed || !dedicatedProcess) {
            runCatching { reply.send(Message.obtain(null, FAILURE)) }
            return@Handler true
        }
        claimed = true // One native request per process lifetime; no hidden queue.
        val data = request.data
        runCatching { reply.send(Message.obtain(null, STARTED, Process.myPid(), 0)) }
        worker.execute {
            try {
                val input = File(requireNotNull(data.getString("input"))).canonicalFile
                require(input.parentFile == File(cacheDir, "diarization-input").canonicalFile)
                require(input.length() in 6400..(120L * 16000 * 4) && input.length() % 4 == 0L)
                val model = File(requireNotNull(data.getString("model"))).canonicalFile
                require(model.parentFile == File(filesDir, "diarization-models").canonicalFile)
                DiarizationModelStore(this).verify(model)
                val samples = DataInputStream(input.inputStream().buffered()).use { stream ->
                    FloatArray((input.length() / 4).toInt()) { stream.readFloat() }
                }
                val result = OfflineDiarization.process(PcmAudio(samples, 16000), model)
                require(result.turns.size <= DiarizationReply.MAX_ITEMS && result.windows.size <= DiarizationReply.MAX_ITEMS)
                val output = Bundle().apply {
                    putLongArray("starts", result.turns.map { it.startMs }.toLongArray())
                    putLongArray("ends", result.turns.map { it.endMs }.toLongArray())
                    putStringArrayList("speakers", ArrayList(result.turns.map { it.speakerId }))
                    putBooleanArray("eligible", result.turns.map { it.attributionEligible }.toBooleanArray())
                    putLongArray("windowStarts", result.windows.map { it.startMs }.toLongArray())
                    putLongArray("windowEnds", result.windows.map { it.endMs }.toLongArray())
                    putLong("load", result.loadMs); putLong("process", result.processMs)
                }
                reply.send(Message.obtain(null, RESULT).apply { this.data = output })
            } catch (e: Exception) {
                runCatching { reply.send(Message.obtain(null, FAILURE).apply {
                    this.data = Bundle().apply { putString("error", e.javaClass.simpleName) }
                }) }
            } catch (_: LinkageError) {
                runCatching { reply.send(Message.obtain(null, FAILURE)) }
            } catch (_: OutOfMemoryError) {
                runCatching { reply.send(Message.obtain(null, FAILURE)) }
            }
        }
        true
    })
    override fun onBind(intent: Intent): IBinder = messenger.binder
    override fun onDestroy() {
        worker.shutdownNow()
        super.onDestroy()
        // Interrupting a Java executor cannot stop JNI. This service is the only
        // component in :diarization, so final unbind ends its OWN process. Never
        // kill a PID supplied by a message or the application/UI process.
        if (dedicatedProcess) Process.killProcess(Process.myPid())
    }
    companion object {
        const val RUN = 1
        const val STARTED = 2
        const val RESULT = 3
        const val FAILURE = 4
    }
}
