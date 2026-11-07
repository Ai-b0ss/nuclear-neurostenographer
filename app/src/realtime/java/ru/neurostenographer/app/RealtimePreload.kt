package ru.neurostenographer.app

import android.content.Context
import ru.neurostenographer.core.NemotronChunkConfig

/**
 * Loads the live models (A3, Silero VAD, C2) while the live screen is open, before the user taps Start:
 * on HONOR loading takes ~7 s, which was the whole tail of the first phrases' text latency.
 * At most one preloaded instance; a session takes it (ownership moves to the session, which closes it).
 * Leaving the screen without recording releases it, so ~1 GB is not held in the background.
 */
object RealtimePreload {
    private val lock = Object()
    private var loading = false
    private var ready: RealtimeNative? = null
    private var releaseWhenLoaded = false

    fun start(context: Context) {
        val app = context.applicationContext
        synchronized(lock) {
            releaseWhenLoaded = false
            if (loading || ready != null) return
            loading = true
        }
        Thread({
            val native = runCatching { RealtimeNative(app, NemotronChunkConfig.FAST) }.getOrNull()
            synchronized(lock) {
                loading = false
                if (releaseWhenLoaded) { native?.close(); releaseWhenLoaded = false } else ready = native
                lock.notifyAll()
            }
        }, "RealtimePreload").start()
    }

    /** Waits for a load in progress (up to [timeoutMs]); null means the caller loads models itself. */
    fun take(timeoutMs: Long = 60_000): RealtimeNative? = synchronized(lock) {
        val deadline = System.currentTimeMillis() + timeoutMs
        while (loading && System.currentTimeMillis() < deadline) lock.wait(maxOf(1, deadline - System.currentTimeMillis()))
        ready.also { ready = null }
    }

    /** True once models are in memory (UI hint and on-device latency test). */
    val isReady: Boolean get() = synchronized(lock) { ready != null }

    fun release() = synchronized(lock) {
        if (loading) releaseWhenLoaded = true
        ready?.close(); ready = null
    }
}
