package ru.neurostenographer.app

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.AudioRecordingConfiguration
import android.media.AudioTimestamp
import android.media.MediaRecorder
import android.os.Build
import android.os.Handler
import android.os.Looper
import androidx.annotation.RequiresPermission
import java.util.concurrent.atomic.AtomicBoolean

/** Only this thread reads/releases AudioRecord; inference cannot delay capture. */
class RealtimeCapture(private val context: Context, val journal: RealtimeJournal, private val seconds: Int = 3600) {
    private val stopping = AtomicBoolean(false)
    private var audio: AudioRecord? = null
    private var worker: Thread? = null
    @Volatile var maxReadGapMs = 0L
        private set
    @Volatile var hardwareFramePosition = 0L
        private set
    @Volatile var timestampSamples = 0
        private set
    private val manager = context.getSystemService(AudioManager::class.java)
    private val callback = object : AudioManager.AudioRecordingCallback() {
        override fun onRecordingConfigChanged(configs: MutableList<AudioRecordingConfiguration>) {
            if (Build.VERSION.SDK_INT >= 29 && configs.any { it.clientAudioSessionId == audio?.audioSessionId && it.isClientSilenced }) {
                journal.failure = "MICROPHONE_SILENCED_BY_SYSTEM"; requestStop()
            }
        }
    }
    @RequiresPermission(Manifest.permission.RECORD_AUDIO)
    fun start() {
        check(worker == null)
        check(context.checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED)
        require(seconds in 1..3600)
        val min = AudioRecord.getMinBufferSize(16000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        require(min in 1..1_048_576)
        val recorder = AudioRecord(MediaRecorder.AudioSource.MIC, 16000, AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT, maxOf(min * 4, 16384))
        try {
            check(recorder.state == AudioRecord.STATE_INITIALIZED)
            recorder.startRecording()
            check(recorder.recordingState == AudioRecord.RECORDSTATE_RECORDING)
            audio = recorder
            manager.registerAudioRecordingCallback(callback, Handler(Looper.getMainLooper()))
        } catch (e: Throwable) { recorder.release(); throw e }
        worker = Thread({
            try {
                val samples = ShortArray(512)
                val began = System.nanoTime()
                var last = began
                val stamp = AudioTimestamp()
                while (!stopping.get() && journal.samples < seconds * 16000L && System.nanoTime() - began < seconds * 1_000_000_000L) {
                    val count = recorder.read(samples, 0, minOf(512L, seconds * 16000L - journal.samples).toInt(), AudioRecord.READ_NON_BLOCKING)
                    check(count >= 0) { "AudioRecord.read=$count" }
                    if (count == 0) { Thread.sleep(2); continue }
                    val now = System.nanoTime()
                    maxReadGapMs = maxOf(maxReadGapMs, (now - last) / 1_000_000); last = now
                    journal.append(samples, count)
                    if (recorder.getTimestamp(stamp, AudioTimestamp.TIMEBASE_MONOTONIC) == AudioRecord.SUCCESS) {
                        hardwareFramePosition = stamp.framePosition; timestampSamples++
                    }
                }
            } catch (e: Throwable) { journal.failure = "${e.javaClass.simpleName}: ${e.message}" }
            finally {
                runCatching { manager.unregisterAudioRecordingCallback(callback) }
                runCatching { recorder.stop() }.onFailure { journal.failure = "Microphone stop: ${it.message}" }
                runCatching { recorder.release() }.onFailure { journal.failure = "Microphone release: ${it.message}" }
                runCatching { journal.finish() }.onFailure { journal.failure = "WAV finalization: ${it.message}" }
            }
        }, "RealtimeCapture").also { it.start() }
    }
    fun requestStop() { stopping.set(true) }
    fun join(timeoutMs: Long): Boolean { worker?.join(timeoutMs); return worker?.isAlive != true }
    val isRunning get() = worker?.isAlive == true
}
