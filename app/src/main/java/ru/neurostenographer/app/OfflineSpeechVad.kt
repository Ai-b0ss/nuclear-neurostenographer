package ru.neurostenographer.app

import android.content.Context
import com.k2fsa.sherpa.onnx.SileroVadModelConfig
import com.k2fsa.sherpa.onnx.Vad
import com.k2fsa.sherpa.onnx.VadModelConfig
import ru.neurostenographer.core.AudioWindow
import ru.neurostenographer.core.PcmAudio
import java.io.File
import java.security.MessageDigest

/**
 * Independent speech detector: Nemotron establishes WHO speaks, not the
 * exclusive source of evidence for WHERE speech exists.
 *
 * Uses exactly the same pinned Silero model already bundled for live mode.
 * The optional result is merged with Nemotron turns before GigaAM decoding.
 */
object OfflineSpeechVad {
    private const val MODEL_SHA = "9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6"
    private const val FRAME = 512

    fun detect(context: Context, audio: PcmAudio, checkCancelled: () -> Unit): List<AudioWindow>? {
        if (!BuildConfig.REALTIME) return null
        require(audio.sampleRate == 16000)
        checkCancelled()
        val data = context.assets.open("silero_vad.onnx").use { it.readBytes() }
        val digest = MessageDigest.getInstance("SHA-256")
        val hash = digest.digest(data).joinToString("") { "%02x".format(it) }
        check(hash == MODEL_SHA) { "Silero VAD model integrity check failed" }
        val model = File(context.filesDir, "offline-silero-vad.onnx")
        val currentOk = model.isFile && model.length() == data.size.toLong() &&
            MessageDigest.getInstance("SHA-256").digest(model.readBytes())
                .joinToString("") { "%02x".format(it) } == MODEL_SHA
        if (!currentOk) {
            val temp = File(context.filesDir, "offline-silero-vad.part")
            try {
                temp.writeBytes(data)
                if (model.exists()) check(model.delete())
                check(temp.renameTo(model)) { "Cannot install offline Silero VAD" }
            } finally { temp.delete() }
        }

        val spans = mutableListOf<AudioWindow>()
        val frame = FloatArray(FRAME)
        val samples = audio.samples
        var firstActive = -1
        var lastActive = -1
        val vad = Vad(config = VadModelConfig(
            sileroVadModelConfig = SileroVadModelConfig(model = model.absolutePath, windowSize = FRAME),
            numThreads = 1
        ))
        try {
            var offset = 0
            var index = 0
            while (offset < samples.size) {
                if (index % 256 == 0) checkCancelled()
                java.util.Arrays.fill(frame, 0f)
                System.arraycopy(samples, offset, frame, 0, minOf(FRAME, samples.size - offset))
                if (vad.compute(frame) >= 0.5f) {
                    if (firstActive < 0) firstActive = index
                    lastActive = index
                } else if (firstActive >= 0 && index - lastActive >= 10) {
                    if (lastActive - firstActive + 1 >= 4) {
                        val begin = (firstActive * FRAME * 1000L / 16000L - 160L).coerceAtLeast(0)
                        val end = ((lastActive + 1L) * FRAME * 1000L / 16000L + 160L).coerceAtMost(audio.durationMs)
                        if (end > begin) spans += AudioWindow(begin, end)
                    }
                    firstActive = -1
                    lastActive = -1
                }
                offset += FRAME
                index++
            }
            if (firstActive >= 0 && lastActive - firstActive + 1 >= 4) {
                val begin = (firstActive * FRAME * 1000L / 16000L - 160L).coerceAtLeast(0)
                val end = ((lastActive + 1L) * FRAME * 1000L / 16000L + 160L).coerceAtMost(audio.durationMs)
                if (end > begin) spans += AudioWindow(begin, end)
            }
        } finally { vad.release() }
        checkCancelled()
        return spans
    }
}
