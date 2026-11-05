package ru.neurostenographer.tools

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import ru.neurostenographer.core.*
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer

/** Actual native C2 on Windows; accelerated synthetic replay, never Android/latency evidence. */
fun main(args: Array<String>) {
    val model = File(args[0]); val wav = File(args[1]); val out = File(args[2]).apply { mkdirs() }
    fun floats(name: String): FloatArray {
        val data = File(model, name).readBytes()
        return FloatArray(data.size / 4).also { ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(it) }
    }
    val filters = floats("mel_filters.bin"); val hann = floats("hann400.bin"); val silence = floats("silence_embeds.bin")
    val audio = wav.inputStream().use { PcmWav.read(it) }
    val env = OrtEnvironment.getEnvironment()
    OrtSession.SessionOptions().use { options ->
        options.setIntraOpNumThreads(4)
        env.createSession(File(model, "model.int8.ir9.onnx").absolutePath, options).use { session ->
            val runner = NemotronChunkRunner { mel, frames, length, history, contextFrames ->
                val inputs = linkedMapOf<String, OnnxTensor>()
                try {
                    inputs["chunk_mel"] = OnnxTensor.createTensor(env, FloatBuffer.wrap(mel), longArrayOf(1, frames.toLong(), 128))
                    inputs["chunk_mel_length"] = OnnxTensor.createTensor(env, length.toLong())
                    inputs["context_embeds"] = OnnxTensor.createTensor(env, FloatBuffer.wrap(history), longArrayOf(1, contextFrames.toLong(), 512))
                    inputs["context_length"] = OnnxTensor.createTensor(env, contextFrames.toLong())
                    session.run(inputs).use { result ->
                        val logits = result[0] as OnnxTensor; val embeds = result[1] as OnnxTensor
                        NemotronStep(FloatArray(logits.floatBuffer.remaining()).also { logits.floatBuffer.get(it) }, logits.info.shape[1].toInt(),
                            FloatArray(embeds.floatBuffer.remaining()).also { embeds.floatBuffer.get(it) }, embeds.info.shape[1].toInt())
                    }
                } finally { inputs.values.forEach { it.close() } }
            }
            fun write(name: String, raw: List<ClusterTurn>) {
                File(out, "$name.tsv").writeText(raw.joinToString("") { "${(it.startSeconds * 1000).toLong()}\t${(it.endSeconds * 1000).toLong()}\t${it.cluster}\n" })
            }
            val baseline = NemotronDiarizer.diarize(audio.samples, filters, hann, silence, runner)
            write("original-offline", baseline)
            fun run(name: String, config: NemotronChunkConfig, duration: Long = audio.samples.size.toLong(), adaptive: Boolean = false): List<ClusterTurn> {
                val stream = NemotronStreaming(filters, hann, silence, runner, config)
                var available = 0L; var maxContext = 0; var maxRead = 0; var callsBeforeSwitch = 0
                val began = System.nanoTime()
                while (available < duration) {
                    // Accelerated arrival in true 512-sample frame units.
                    available = minOf(duration, available + 512)
                    if (adaptive && stream.calls >= 3 && stream.config == NemotronChunkConfig.FAST) {
                        callsBeforeSwitch = stream.calls; stream.config = NemotronChunkConfig.FALLBACK
                    }
                    while (stream.canStep(available, false)) {
                        stream.step(available, false) { first, count ->
                            check(first >= 0 && first + count <= available) { "Future context leak" }
                            maxRead = maxOf(maxRead, count)
                            FloatArray(count) { audio.samples[((first + it) % audio.samples.size).toInt()] }
                        }
                        maxContext = maxOf(maxContext, stream.contextFrames)
                    }
                }
                while (stream.canStep(duration, true)) {
                    stream.step(duration, true) { first, count ->
                        check(first + count <= duration)
                        maxRead = maxOf(maxRead, count)
                        FloatArray(count) { audio.samples[((first + it) % audio.samples.size).toInt()] }
                    }
                    maxContext = maxOf(maxContext, stream.contextFrames)
                }
                val turns = stream.snapshot(duration)
                check(stream.committedSamples in duration..duration + 160)
                check(maxContext <= config.fifo + NemotronConfig.CACHE)
                check(maxRead <= (340 + 40) * 1280 + 1024)
                write(name, turns)
                val time = (System.nanoTime() - began) / 1_000_000
                File(out, "$name.json").writeText("""{"status":"PASS","scope":"WINDOWS_NATIVE_C2_ACCELERATED_SYNTHETIC_REPLAY_NOT_ANDROID","audio_samples":$duration,"audio_ms":${duration / 16},"process_ms":$time,"calls":${stream.calls},"max_context_frames":$maxContext,"max_read_samples":$maxRead,"turns":${turns.size},"speakers":${turns.map { it.cluster }.distinct().size},"causal_reads":true,"calls_before_switch":$callsBeforeSwitch}""")
                println("$name: calls=${stream.calls} context=$maxContext wall_ms=$time")
                return turns
            }
            val offline = run("incremental-offline", NemotronChunkConfig.OFFLINE)
            check(DiarizationTimeline.canonicalize(offline, audio.durationMs) == DiarizationTimeline.canonicalize(baseline, audio.durationMs)) {
                "Original/offline-config parity failed"
            }
            run("fast", NemotronChunkConfig.FAST)
            run("fallback", NemotronChunkConfig.FALLBACK)
            run("adaptive-20min", NemotronChunkConfig.FAST, 20 * 60 * 16000L, adaptive = true)
            run("fallback-60min", NemotronChunkConfig.FALLBACK, 60 * 60 * 16000L)
            File(out, "parity.json").writeText("""{"status":"PASS","original_offline_exact_canonical_turn_parity":true,"future_reads":0,"scope":"WINDOWS_NATIVE_C2_ONLY_NO_ASR_NO_PHONE"}""")
        }
    }
}
