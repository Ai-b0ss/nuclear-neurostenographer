package ru.neurostenographer.tools

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import ru.neurostenographer.core.*
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import java.lang.management.ManagementFactory

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
            val trace = StringBuilder()
            var activeConfig = NemotronChunkConfig.OFFLINE
            var emittedEmbeddings = 0
            var chronological = true
            var emitted = BooleanArray(0)
            var captureEmbeddings = true
            val embeddingRows = mutableListOf<FloatArray>()
            val runner = NemotronChunkRunner { mel, frames, length, history, contextFrames ->
                val inputs = linkedMapOf<String, OnnxTensor>()
                try {
                    inputs["chunk_mel"] = OnnxTensor.createTensor(env, FloatBuffer.wrap(mel), longArrayOf(1, frames.toLong(), 128))
                    inputs["chunk_mel_length"] = OnnxTensor.createTensor(env, length.toLong())
                    inputs["context_embeds"] = OnnxTensor.createTensor(env, FloatBuffer.wrap(history), longArrayOf(1, contextFrames.toLong(), 512))
                    inputs["context_length"] = OnnxTensor.createTensor(env, contextFrames.toLong())
                    session.run(inputs).use { result ->
                        val logits = result[0] as OnnxTensor; val embeds = result[1] as OnnxTensor
                        val step = NemotronStep(FloatArray(logits.floatBuffer.remaining()).also { logits.floatBuffer.get(it) }, logits.info.shape[1].toInt(),
                            FloatArray(embeds.floatBuffer.remaining()).also { embeds.floatBuffer.get(it) }, embeds.info.shape[1].toInt())
                        fun counts(first: Int, last: Int) = (0..7).joinToString(",") { s ->
                            (first until last).count { step.logits[it * 8 + s] > 0 }.toString()
                        }
                        val commit = minOf(activeConfig.chunk, (frames + 7) / 8)
                        val from = contextFrames * 8
                        val until = (contextFrames + commit) * 8
                        chronological = chronological && contextFrames == emittedEmbeddings
                        val changed = if (chronological) emitted.indices.count { emitted[it] != (step.logits[it] > 0) } else -1
                        trace.append("$frames\t$length\t$contextFrames\t${counts(0, from)}\t${counts(from, until)}\t${counts(until, step.logitFrames)}\t$changed\n")
                        // Diagnostic comparison only: never feed labels or revised logits to inference.
                        if (chronological) emitted += BooleanArray(commit * 64) { step.logits[from * 8 + it] > 0 }
                        emittedEmbeddings += commit
                        if (captureEmbeddings) for (row in contextFrames until contextFrames + commit)
                            embeddingRows += step.embeds.copyOfRange(row * 512, (row + 1) * 512)
                        step
                    }
                } finally { inputs.values.forEach { it.close() } }
            }
            fun write(name: String, raw: List<ClusterTurn>) {
                File(out, "$name.tsv").writeText(raw.joinToString("") { "${(it.startSeconds * 1000).toLong()}\t${(it.endSeconds * 1000).toLong()}\t${it.cluster}\n" })
            }
            val baseline = NemotronDiarizer.diarize(audio.samples, filters, hann, silence, runner)
            write("original-offline", baseline)
            captureEmbeddings = false
            File(out, "encoder-embeddings.bin").outputStream().use { file ->
                for (row in embeddingRows) {
                    val bytes = ByteBuffer.allocate(512 * 4).order(ByteOrder.LITTLE_ENDIAN)
                    row.forEach { bytes.putFloat(it) }; file.write(bytes.array())
                }
            }
            embeddingRows.clear()
            fun run(name: String, config: NemotronChunkConfig, duration: Long = audio.samples.size.toLong(), adaptive: Boolean = false, revise: Boolean = false): List<ClusterTurn> {
                trace.clear()
                activeConfig = config; emittedEmbeddings = 0; chronological = true; emitted = BooleanArray(0)
                val stream = NemotronStreaming(filters, hann, silence, runner, config, revise)
                var available = 0L; var maxContext = 0; var maxRead = 0; var callsBeforeSwitch = 0
                val began = System.nanoTime()
                val os = ManagementFactory.getOperatingSystemMXBean() as com.sun.management.OperatingSystemMXBean
                val cpuStart = os.processCpuTime
                while (available < duration) {
                    // Accelerated arrival in true 512-sample frame units.
                    available = minOf(duration, available + 512)
                    if (adaptive && stream.calls >= 3 && stream.config == NemotronChunkConfig.FAST) {
                        callsBeforeSwitch = stream.calls; stream.config = NemotronChunkConfig.FALLBACK
                        activeConfig = stream.config
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
                File(out, "$name-trace.tsv").writeText("mel_frames\tmel_length\tcontext_frames\thistory_positive_rows_per_slot\tcommitted_positive_rows_per_slot\tright_positive_rows_per_slot\thistory_bits_different_from_emitted_or_minus1_after_compression\n" + trace)
                File(out, "$name-cost.json").writeText("""{"cpu_ms":${(os.processCpuTime - cpuStart) / 1_000_000},"compute_rtf":${time.toDouble() / (duration / 16.0)},"first_ready_audio_ms":${((config.chunk + config.right) * 1280 + 256) / 16},"pss":"NOT_APPLICABLE_WINDOWS","device_latency":"NOT_RUN"}""")
                File(out, "$name.json").writeText("""{"status":"PASS","scope":"WINDOWS_NATIVE_C2_ACCELERATED_SYNTHETIC_REPLAY_NOT_ANDROID","audio_samples":$duration,"audio_ms":${duration / 16},"process_ms":$time,"calls":${stream.calls},"max_context_frames":$maxContext,"max_read_samples":$maxRead,"revised_frames":${stream.revisedFrames},"heap_used_bytes":${Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory()},"timeline_capacity_bytes":360001,"turns":${turns.size},"speakers":${turns.map { it.cluster }.distinct().size},"causal_reads":true,"calls_before_switch":$callsBeforeSwitch}""")
                println("$name: calls=${stream.calls} context=$maxContext wall_ms=$time")
                return turns
            }
            if (args.getOrNull(3) == "final-hour") {
                run("selected-final-60min", NemotronChunkConfig.OFFLINE, 60 * 60 * 16000L)
                return
            }
            val offline = run("incremental-offline", NemotronChunkConfig.OFFLINE)
            check(DiarizationTimeline.canonicalize(offline, audio.durationMs) == DiarizationTimeline.canonicalize(baseline, audio.durationMs)) {
                "Original/offline-config parity failed"
            }
            run("fast", NemotronChunkConfig.FAST)
            run("fallback", NemotronChunkConfig.FALLBACK)
            run("revised-fast", NemotronChunkConfig.FAST, revise = true)
            run("revised-offline", NemotronChunkConfig.OFFLINE, revise = true)
            if (args.getOrNull(3) == "hour") {
                run("baseline-fast-60min", NemotronChunkConfig.FAST, 60 * 60 * 16000L)
                run("revised-fast-60min", NemotronChunkConfig.FAST, 60 * 60 * 16000L, revise = true)
                run("final-offline-60min", NemotronChunkConfig.OFFLINE, 60 * 60 * 16000L, revise = true)
            } else if (args.getOrNull(3) == "diagnostic") {
                run("short-right40", NemotronChunkConfig(45, 40, 264, 222))
                run("long-right6", NemotronChunkConfig(120, 6, 264, 222))
            } else {
                run("adaptive-20min", NemotronChunkConfig.FAST, 20 * 60 * 16000L, adaptive = true)
                run("fallback-60min", NemotronChunkConfig.FALLBACK, 60 * 60 * 16000L)
            }
            File(out, "parity.json").writeText("""{"status":"PASS","original_offline_exact_canonical_turn_parity":true,"future_reads":0,"scope":"WINDOWS_NATIVE_C2_ONLY_NO_ASR_NO_PHONE"}""")
        }
    }
}
