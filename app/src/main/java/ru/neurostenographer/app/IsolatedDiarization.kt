package ru.neurostenographer.app

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.*
import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.io.DataOutputStream
import java.io.File
import ru.neurostenographer.core.*

class DiarizationUnavailable(message: String) : Exception(message)

object IsolatedDiarization {
    private val lease = Mutex()
    private var pendingWorkerDeath: CompletableDeferred<Unit>? = null
    private var pendingWorkerBinder: IBinder? = null

    /** Accept only observed Binder death. Android can deliver linkToDeath later
     * than the underlying binder turns dead; isBinderAlive() is a second read-only
     * observation of that same remote endpoint. Neither a missing process in a
     * process list nor elapsed time alone authorizes a new native worker.
     */
    internal suspend fun awaitPriorWorkerExit(
        death: Deferred<Unit>?, graceMs: Long = 15_000,
        binderAlive: (() -> Boolean)? = null
    ) {
        if (death == null) return
        val confirmed = withTimeoutOrNull(graceMs) {
            while (true) {
                if (death.isCompleted) {
                    death.await()
                    break
                }
                if (binderAlive?.invoke() == false) break
                delay(50)
            }
            true
        }
        if (confirmed != true)
            throw DiarizationUnavailable("Предыдущий процесс диаризации ещё завершается")
    }
    suspend fun process(context: Context, audio: PcmAudio, model: File,
                        clusteringThreshold: Float = OfflineDiarization.THRESHOLD,
                        onWorkerStarted: (Int) -> Unit = {}): DiarizationOutput = withContext(Dispatchers.IO) {
        // Never let callers silently change production inference settings.
        require(OfflineDiarization.validThreshold(clusteringThreshold))
        require(BuildConfig.DEBUG || clusteringThreshold == OfflineDiarization.THRESHOLD)
        lease.withLock {
            // A previous timed-out cleanup must not permit another native task while
            // the old process may still own samples/models. A later observed death
            // permits recovery; no PID-based kill/retry guesses.
            // A burst of sequential calls can reach this guard just before the
            // prior Binder death is delivered. Await that exact signal briefly;
            // never start another worker on an unconfirmed exit.
            awaitPriorWorkerExit(pendingWorkerDeath) {
                pendingWorkerBinder?.isBinderAlive != false
            }
            pendingWorkerDeath = null
            pendingWorkerBinder = null
            require(audio.sampleRate == 16000 && audio.samples.size in 1600..(120 * 16000))
            val root = File(context.cacheDir, "diarization-input").apply { mkdirs() }
            val input = File.createTempFile("audio-", ".pcm", root)
            try {
                DataOutputStream(input.outputStream().buffered()).use { stream ->
                    audio.samples.forEachIndexed { i, value ->
                        if (i % 16000 == 0) currentCoroutineContext().ensureActive()
                        stream.writeFloat(value)
                    }
                }
                try {
                    withTimeout(10 * 60 * 1000L) {
                        awaitWorker(context, input, model, audio.durationMs, clusteringThreshold, onWorkerStarted)
                    }
                } catch (_: TimeoutCancellationException) { throw DiarizationUnavailable("Превышено время диаризации") }
            } finally { input.delete() }
        }
    }

    private suspend fun awaitWorker(context: Context, input: File, model: File, audioMs: Long,
                                    clusteringThreshold: Float,
                                    onWorkerStarted: (Int) -> Unit): DiarizationOutput = withContext(Dispatchers.Main.immediate) {
        val result = CompletableDeferred<DiarizationOutput>()
        var workerDeath: CompletableDeferred<Unit>? = null
        var workerBinder: IBinder? = null
        val receiver = Messenger(Handler(Looper.getMainLooper()) { message ->
            if (!result.isActive) return@Handler true
            try {
                when (message.what) {
                    DiarizationService.STARTED -> onWorkerStarted(message.arg1)
                    DiarizationService.FAILURE -> result.completeExceptionally(DiarizationUnavailable("Ошибка процесса диаризации"))
                    DiarizationService.RESULT -> {
                        val data = message.data
                        val starts = requireNotNull(data.getLongArray("starts"))
                        val ends = requireNotNull(data.getLongArray("ends"))
                        val names = requireNotNull(data.getStringArrayList("speakers"))
                        val eligible = requireNotNull(data.getBooleanArray("eligible"))
                        val ws = requireNotNull(data.getLongArray("windowStarts"))
                        val we = requireNotNull(data.getLongArray("windowEnds"))
                        val loadMs = data.getLong("load", -1)
                        val processMs = data.getLong("process", -1)
                        val validated = DiarizationReply.validate(audioMs, starts, ends, names, eligible, ws, we,
                            loadMs, processMs)
                        result.complete(DiarizationOutput(validated.turns, loadMs, processMs, validated.windows))
                    }
                }
            } catch (_: Exception) { result.completeExceptionally(DiarizationUnavailable("Некорректный ответ диаризации")) }
            true
        })
        val connection = object : ServiceConnection {
            override fun onServiceConnected(name: ComponentName, binder: IBinder) {
                if (!result.isActive) return
                val death = CompletableDeferred<Unit>()
                workerDeath = death
                workerBinder = binder
                try {
                    binder.linkToDeath({ death.complete(Unit); disconnected() }, 0)
                    Messenger(binder).send(Message.obtain(null, DiarizationService.RUN).apply {
                        replyTo = receiver
                        data = Bundle().apply {
                            putString("input", input.absolutePath)
                            putString("model", model.absolutePath)
                            putFloat("clusteringThreshold", clusteringThreshold)
                        }
                    })
                } catch (_: RemoteException) { death.complete(Unit); disconnected() }
            }
            private fun disconnected() {
                result.completeExceptionally(DiarizationUnavailable("Процесс диаризации завершился; говорящие неизвестны"))
            }
            override fun onServiceDisconnected(name: ComponentName) = disconnected()
            override fun onBindingDied(name: ComponentName) = disconnected()
            override fun onNullBinding(name: ComponentName) = disconnected()
        }
        val bound = context.bindService(Intent(context, DiarizationService::class.java), connection, Context.BIND_AUTO_CREATE)
        if (!bound) throw DiarizationUnavailable("Не удалось запустить процесс диаризации")
        try { result.await() }
        finally {
            result.cancel()
            // Main-thread cleanup cannot race a delayed onServiceConnected into
            // starting work after cancellation. Final unbind destroys the private
            // service, which terminates its own native process.
            withContext(NonCancellable) {
                try { context.unbindService(connection) }
                finally {
                    workerDeath?.let { death ->
                        pendingWorkerDeath = death
                        pendingWorkerBinder = workerBinder
                        // Do not replace a successful model result with a cleanup
                        // timeout. A subsequent request must still check this worker
                        // until death is confirmed by either Binder observation.
                        try {
                            awaitPriorWorkerExit(death, 5_000) {
                                workerBinder?.isBinderAlive != false
                            }
                        } catch (_: DiarizationUnavailable) {
                            // Keep the pending death and Binder for the next call.
                        }
                    }
                }
            }
        }
    }
}
