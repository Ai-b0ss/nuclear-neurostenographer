package ru.neurostenographer.app

import android.Manifest
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import androidx.annotation.RequiresPermission
import java.io.File
import ru.neurostenographer.core.BoundedWavRecorder
import ru.neurostenographer.core.PcmCapture

/** Android adapter; resource ownership/limits are exercised in core tests. */
interface WavRecording {
    val isRunning: Boolean
    @RequiresPermission(Manifest.permission.RECORD_AUDIO)
    fun start()
    fun requestStop()
    fun stop(): File
}

class RecordWav(private val output: File) : WavRecording {
    private var recorder: BoundedWavRecorder? = null
    override val isRunning: Boolean get() = recorder?.isRunning == true

    @RequiresPermission(Manifest.permission.RECORD_AUDIO)
    override fun start() {
        check(recorder == null) { "Recorder is one-shot" }
        val min = AudioRecord.getMinBufferSize(16000, AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT)
        require(min in 1..1_048_576) { "Unsupported microphone configuration" }
        val audio = AudioRecord(MediaRecorder.AudioSource.MIC, 16000,
            AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, min * 4)
        val session = BoundedWavRecorder(output, object : PcmCapture {
            override fun start() {
                require(audio.state == AudioRecord.STATE_INITIALIZED) { "Microphone initialization failed" }
                audio.startRecording()
                check(audio.recordingState == AudioRecord.RECORDSTATE_RECORDING) { "Microphone did not start" }
            }
            override fun read(samples: ShortArray): Int =
                audio.read(samples, 0, samples.size, AudioRecord.READ_NON_BLOCKING)

            override fun close() {
                try {
                    if (audio.recordingState == AudioRecord.RECORDSTATE_RECORDING) audio.stop()
                } finally { audio.release() }
            }
        })
        recorder = session
        session.start()
    }

    override fun requestStop() { recorder?.requestStop() }
    override fun stop(): File = requireNotNull(recorder) { "No recording started" }.stop()
}
