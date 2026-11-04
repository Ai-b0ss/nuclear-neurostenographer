package ru.neurostenographer.app

import ru.neurostenographer.core.*
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

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
    fun install(filesDir: File, input: java.io.InputStream): File {
        val root = File(filesDir, "nemotron-models").apply { mkdirs() }
        val stage = File(root, "current")
        stage.deleteRecursively()
        check(stage.mkdir())
        VerifiedModelBundle(ARTIFACTS).unpack(input, stage)
        return stage
    }

    private fun floats(file: File, count: Int): FloatArray {
        require(file.length() == count * 4L) { "Unexpected size: ${file.name}" }
        val bytes = file.readBytes()
        val out = FloatArray(count)
        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(out)
        return out
    }

    fun process(audio: PcmAudio, model: File, checkCancelled: () -> Unit = {}): DiarizationOutput {
        require(audio.sampleRate == 16000)
        VerifiedModelBundle(ARTIFACTS).verify(model, checkCancelled)
        val filters = floats(File(model, "mel_filters.bin"), NemotronConfig.MELS * NemotronConfig.BINS)
        val hann = floats(File(model, "hann400.bin"), NemotronConfig.WIN)
        val silence = floats(File(model, "silence_embeds.bin"), NemotronConfig.HIDDEN)
        val started = System.nanoTime()
        // Same four-thread cap as C0 and ASR, with the model call now owned by C++.
        val session = CppNemotronSession(File(model, "model.int8.ir9.onnx").absolutePath,
            InferenceThreads.count())
        val loaded = System.nanoTime()
        try {
            val runner = NemotronChunkRunner { chunk, melFrames, melLength, context, contextFrames ->
                session.run(chunk, melFrames, melLength, context, contextFrames)
            }
            val raw = NemotronDiarizer.diarize(audio.samples, filters, hann, silence, runner, checkCancelled)
            val turns = DiarizationTimeline.canonicalize(raw, audio.durationMs)
            return DiarizationOutput(turns, (loaded - started) / 1_000_000, (System.nanoTime() - loaded) / 1_000_000,
                DiarizationTimeline.speechWindows(raw, audio.durationMs))
        } finally {
            session.close()
        }
    }
}
