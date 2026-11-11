package ru.neurostenographer.app

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import ru.neurostenographer.core.*
import java.io.DataInputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import android.util.AtomicFile

/** Prototype C2: Nemotron 3 INT8 through ONNX Runtime 1.17.1, the version already in the APK.
 * Compiled only with -PnemotronPrototype=true; C0 stays the default everywhere.
 */
object NemotronDiarization {
    const val REVISION = "nemotron3-diarization-onnx-4a911fc3/int8-ir9"
    val ARTIFACTS = linkedMapOf(
        "model.int8.ir9.onnx" to PinnedArtifact("c465504c2f3a29242e1b3d894187ae5962be7320bed71a2ae203950285ee6025", 103_726_888),
        "mel_filters.bin" to PinnedArtifact("bce5ec5f194a5913f6508cee5a85512e7bad2352db8fc28f5c6ff75af8b09137", 131_584),
        "hann400.bin" to PinnedArtifact("c427e2029118cf789649e5a4d439b6115d0dd0cbf95dcd22f65e3c848add8c5b", 1600),
        "silence_embeds.bin" to PinnedArtifact("d4417b3c0eabdf7c47032fac2b5b5a7ee83d819a6ddda8fd8eaf74e2b5cc4ac7", 2048),
        "LICENSE" to PinnedArtifact("2ab44b68365473c112f5092211a38f231cb23e50de68b75a13369adbd76a74df", 2619),
        "NOTICE" to PinnedArtifact("29e938a6febe0878b9ab2c8983c342e7d6cae5530964f674dc04312d06d29d71", 3748),
        "CHANGES.txt" to PinnedArtifact("8a58e4b3805b9ea837b38e559d728e64db74896725962847f2359b91bfb88357", 1024)
    )

    /** Verified install into filesDir/nemotron-models, the only folder the worker accepts for C2. */
    @Synchronized fun install(filesDir: File, input: java.io.InputStream): File {
        val root = File(filesDir, "nemotron-models").apply { mkdirs() }
        val stage = File.createTempFile("bundle-", ".stage", root)
        check(stage.delete() && stage.mkdir())
        var installed = false
        try {
            // Validate completely before changing the selected model. A corrupt ZIP,
            // cancelled read or disk error must leave the previous bundle available.
            VerifiedModelBundle(ARTIFACTS).unpack(input, stage)
            val pointer = AtomicFile(File(root, "active.txt"))
            val output = pointer.startWrite()
            try {
                output.write(stage.name.toByteArray(Charsets.UTF_8))
                pointer.finishWrite(output)
            } catch (e: Throwable) {
                pointer.failWrite(output)
                throw e
            }
            installed = true
            // Preserve the previous generation. A separate :diarization worker may have
            // already received its path; deleting it here races its verify/load phase.
            // Reclaim stale generations only when no worker can hold their paths.
            return stage
        } finally {
            if (!installed) stage.deleteRecursively()
        }
    }

    private fun floats(file: File, count: Int): FloatArray {
        require(file.length() == count * 4L) { "Unexpected size: ${file.name}" }
        val bytes = file.readBytes()
        val out = FloatArray(count)
        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(out)
        return out
    }

    fun process(audio: PcmAudio, model: File, checkCancelled: () -> Unit = {},
                onProgress: (Int, Int) -> Unit = { _, _ -> }): DiarizationOutput {
        require(audio.sampleRate == 16000)
        VerifiedModelBundle(ARTIFACTS).verify(model, checkCancelled)
        val filters = floats(File(model, "mel_filters.bin"), NemotronConfig.MELS * NemotronConfig.BINS)
        val hann = floats(File(model, "hann400.bin"), NemotronConfig.WIN)
        val silence = floats(File(model, "silence_embeds.bin"), NemotronConfig.HIDDEN)
        val started = System.nanoTime()
        val environment = OrtEnvironment.getEnvironment()
        // Same thread count as C0 and ASR, so a phone comparison measures the models, not the settings.
        val options = OrtSession.SessionOptions().apply { setIntraOpNumThreads(InferenceThreads.count()) }
        val session = environment.createSession(File(model, "model.int8.ir9.onnx").absolutePath, options)
        val loaded = System.nanoTime()
        try {
            val runner = NemotronChunkRunner { chunk, melFrames, melLength, context, contextFrames ->
                val inputs = linkedMapOf<String, OnnxTensor>()
                try {
                    inputs["chunk_mel"] = OnnxTensor.createTensor(environment, FloatBuffer.wrap(chunk), longArrayOf(1, melFrames.toLong(), NemotronConfig.MELS.toLong()))
                    inputs["chunk_mel_length"] = OnnxTensor.createTensor(environment, melLength.toLong())
                    inputs["context_embeds"] = OnnxTensor.createTensor(environment, FloatBuffer.wrap(context), longArrayOf(1, contextFrames.toLong(), NemotronConfig.HIDDEN.toLong()))
                    inputs["context_length"] = OnnxTensor.createTensor(environment, contextFrames.toLong())
                    session.run(inputs).use { result ->
                        val logits = result[0] as OnnxTensor
                        val embeds = result[1] as OnnxTensor
                        val logitArray = FloatArray(logits.floatBuffer.remaining()).also { logits.floatBuffer.get(it) }
                        val embedArray = FloatArray(embeds.floatBuffer.remaining()).also { embeds.floatBuffer.get(it) }
                        NemotronStep(logitArray, logits.info.shape[1].toInt(), embedArray, embeds.info.shape[1].toInt())
                    }
                } finally { inputs.values.forEach { it.close() } }
            }
            // Two passes: the second starts with the voices the first one learned (docs/C2_POSTPROCESS_2026-11-06.md).
            val (raw, voices) = if (BuildConfig.GLOBAL_SPEAKER_BOOK)
                NemotronDiarizer.diarizeWithVoiceProfiles(audio.samples, filters, hann, silence,
                    runner, checkCancelled, NemotronPostprocess.PRODUCT, onProgress)
            else NemotronDiarizer.diarize(audio.samples, filters, hann, silence, runner, checkCancelled,
                NemotronPostprocess.PRODUCT, warmSecondPass = true, onProgress = onProgress) to emptyList()
            val turns = DiarizationTimeline.canonicalize(raw, audio.durationMs)
            return DiarizationOutput(turns, (loaded - started) / 1_000_000, (System.nanoTime() - loaded) / 1_000_000,
                DiarizationTimeline.speechWindows(raw, audio.durationMs), voices)
        } finally {
            session.close()
            options.close()
        }
    }
}
