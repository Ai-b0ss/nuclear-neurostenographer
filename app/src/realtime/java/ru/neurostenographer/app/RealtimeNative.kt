package ru.neurostenographer.app

import android.content.Context
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import com.k2fsa.sherpa.onnx.*
import ru.neurostenographer.core.*
import java.io.Closeable
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import java.security.MessageDigest

/** All native objects are used and released on the sole inference worker. */
class RealtimeNative(context: Context, c2Config: NemotronChunkConfig,
                     private val c2Override: File? = null,
                     private val stage: (String) -> Unit = {}) : Closeable {
    private var recognizer: OfflineRecognizer? = null
    private var vad: Vad? = null
    private var options: OrtSession.SessionOptions? = null
    private var session: OrtSession? = null
    lateinit var diarizer: NemotronStreaming
        private set
    /** Full-recording speaker pass after capture: the same C2 offline path as file import (warm second pass +
     * PRODUCT post-processing), reading the journal in blocks. Never shares the FAST live cache. */
    private var finalizer: ((Long, (Long, Int) -> FloatArray, () -> Unit) -> List<ClusterTurn>)? = null
    val hasDiarizer get() = ::diarizer.isInitialized
    var diarizationFailure: String? = null
        private set
    init {
        try {
            val spec = AsrModelSpec.ACTIVE
            check(spec.ctcModel == null)
            val store = AsrModelStore(context)
            stage("verify_install_a3")
            val asr = store.current() ?: context.assets.open(spec.zipName).use { store.install(it) }
            store.verify(asr)
            val vadFile = File(context.filesDir, "silero_vad.onnx")
            val data = context.assets.open("silero_vad.onnx").use { it.readBytes() }
            check(MessageDigest.getInstance("SHA-256").digest(data).joinToString("") { "%02x".format(it) } ==
                "9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6")
            vadFile.writeBytes(data)
            stage("load_silero")
            vad = Vad(config = VadModelConfig(sileroVadModelConfig = SileroVadModelConfig(
                model = vadFile.absolutePath, windowSize = 512), numThreads = 1))
            stage("load_a3")
            recognizer = OfflineRecognizer(config = OfflineRecognizerConfig(
                featConfig = FeatureConfig(sampleRate = 16000, featureDim = 64),
                modelConfig = OfflineAsr.modelConfig(spec, asr), decodingMethod = "greedy_search"))
            stage("verify_install_c2")
            try {
            val c2 = c2Override ?: NemotronBackend.current(context.filesDir)
                ?: context.assets.open("nemotron.zip").use { NemotronBackend.install(context.filesDir, it) }
            VerifiedModelBundle(NemotronDiarization.ARTIFACTS).verify(c2)
            fun floats(name: String): FloatArray {
                val bytes = File(c2, name).readBytes()
                return FloatArray(bytes.size / 4).also {
                    ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(it)
                }
            }
            val env = OrtEnvironment.getEnvironment()
            options = OrtSession.SessionOptions().apply { setIntraOpNumThreads(InferenceThreads.count()) }
            stage("load_c2")
            session = env.createSession(File(c2, "model.int8.ir9.onnx").absolutePath, options)
            val runner = NemotronChunkRunner { mel, frames, length, history, contextFrames ->
                val inputs = linkedMapOf<String, OnnxTensor>()
                try {
                    inputs["chunk_mel"] = OnnxTensor.createTensor(env, FloatBuffer.wrap(mel), longArrayOf(1, frames.toLong(), 128))
                    inputs["chunk_mel_length"] = OnnxTensor.createTensor(env, length.toLong())
                    inputs["context_embeds"] = OnnxTensor.createTensor(env, FloatBuffer.wrap(history), longArrayOf(1, contextFrames.toLong(), 512))
                    inputs["context_length"] = OnnxTensor.createTensor(env, contextFrames.toLong())
                    requireNotNull(session).run(inputs).use { result ->
                        val logits = result[0] as OnnxTensor
                        val embeds = result[1] as OnnxTensor
                        NemotronStep(FloatArray(logits.floatBuffer.remaining()).also { logits.floatBuffer.get(it) }, logits.info.shape[1].toInt(),
                            FloatArray(embeds.floatBuffer.remaining()).also { embeds.floatBuffer.get(it) }, embeds.info.shape[1].toInt())
                    }
                } finally { inputs.values.forEach { it.close() } }
            }
            val filters = floats("mel_filters.bin"); val hann = floats("hann400.bin"); val silence = floats("silence_embeds.bin")
            diarizer = NemotronStreaming(filters, hann, silence, runner, c2Config)
            finalizer = { samples, read, checkpoint ->
                val reader = JournalBlocks(samples, read)
                NemotronDiarizer.diarizeSamples(samples.toInt(), reader::at, filters, hann, silence, runner, checkpoint,
                    NemotronPostprocess.PRODUCT, warmSecondPass = true)
            }
            } catch (e: Exception) {
                diarizationFailure = "${e.javaClass.simpleName}: ${e.message}"
                session?.close(); session = null; options?.close(); options = null
            }
            stage("ready")
        } catch (e: Throwable) { close(); throw e }
    }
    /** Reuse the loaded ORT graph, but never contaminate the full-context pass with FAST cache. */
    fun finalizeSpeakers(samples: Long, read: (Long, Int) -> FloatArray,
                         checkpoint: () -> Unit): List<ClusterTurn> {
        val turns = requireNotNull(finalizer).invoke(samples, read, checkpoint)
        checkpoint()
        return turns
    }
    fun speech(frame: FloatArray): Boolean = requireNotNull(vad).compute(frame) >= 0.5f
    fun decode(samples: FloatArray, span: SampleSpan): Pair<List<RecognizedWord>, RecognizedChunk?> {
        val asr = requireNotNull(recognizer)
        val stream = asr.createStream()
        try {
            stream.acceptWaveform(if (samples.size < 16000) samples.copyOf(16000) else samples, 16000)
            asr.decode(stream)
            val result = asr.getResult(stream)
            if (result.text.isBlank()) return emptyList<RecognizedWord>() to null
            val words = TokenWords.words(result.tokens, result.timestamps, span.startMs, span.endMs)
            return if (!words.isNullOrEmpty()) words to null
                else emptyList<RecognizedWord>() to RecognizedChunk(span.startMs, span.endMs, result.text.trim())
        } finally { stream.release() }
    }
    override fun close() {
        try { session?.close() } finally {
            session = null
            try { options?.close() } finally {
                options = null
                try { recognizer?.release() } finally { recognizer = null; vad?.release(); vad = null }
            }
        }
    }
}
