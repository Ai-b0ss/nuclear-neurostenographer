package ru.neurostenographer.tools

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import ru.neurostenographer.core.*
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer

/**
 * Host (Windows, not phone) C2 run through the product NemotronDiarizer code path.
 * args: modelDir outDir wavList [params.properties]
 * Writes <name>.logits.f32 ([frames, 8] little-endian), <name>.raw.tsv and, with params, <name>.pp.tsv.
 * Fails if binarize(RAW) differs from the original per-frame "logit > 0" loop on any file.
 */
fun main(args: Array<String>) {
    val model = File(args[0]); val out = File(args[1]).apply { mkdirs() }
    val wavs = File(args[2]).readLines().map { it.trim() }.filter { it.isNotEmpty() }.map(::File)
    val pp = args.getOrNull(3)?.let { path ->
        val p = java.util.Properties().apply { File(path).inputStream().use { load(it) } }
        fun f(k: String) = p.getProperty(k)!!.toFloat()
        NemotronPostprocess(f("onset"), f("offset"), f("ov_onset"), f("pad_on"), f("pad_off"), f("min_on"), f("min_off"))
    }
    fun floats(name: String): FloatArray {
        val data = File(model, name).readBytes()
        return FloatArray(data.size / 4).also { ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(it) }
    }
    val filters = floats("mel_filters.bin"); val hann = floats("hann400.bin"); val silence = floats("silence_embeds.bin")
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
            for (wav in wavs) {
                val t0 = System.nanoTime()
                // A saved *.logits.f32 skips inference: used for the Kotlin/Python post-processing parity check.
                val saved = wav.name.endsWith(".logits.f32")
                val name = if (saved) wav.name.removeSuffix(".logits.f32") else wav.nameWithoutExtension
                val frame = if (saved) {
                    val bytes = wav.readBytes()
                    val l = FloatArray(bytes.size / 4).also { ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(it) }
                    NemotronFrameLogits(l, l.size / NemotronConfig.SPEAKERS)
                } else {
                    val audio = wav.inputStream().use { PcmWav.read(it) }
                    NemotronDiarizer.frameLogits(audio.samples, filters, hann, silence, runner)
                }
                val ms = (System.nanoTime() - t0) / 1_000_000
                if (!saved) ByteBuffer.allocate(frame.logits.size * 4).order(ByteOrder.LITTLE_ENDIAN).also { it.asFloatBuffer().put(frame.logits) }
                    .array().let { File(out, "$name.logits.f32").writeBytes(it) }
                val raw = NemotronDiarizer.binarize(frame, NemotronPostprocess.RAW)
                // Same turns at the millisecond resolution DiarizationTimeline.canonicalize keeps.
                fun msKey(turns: List<ClusterTurn>) = turns.map { Triple(Math.round(it.startSeconds * 1000.0), Math.round(it.endSeconds * 1000.0), it.cluster) }
                check(msKey(raw) == msKey(legacy(frame))) { "RAW post-processing differs from the original loop on $name" }
                fun tsv(turns: List<ClusterTurn>) = turns.joinToString("") { "${it.startSeconds}\t${it.endSeconds}\t${it.cluster}\n" }
                File(out, "$name.raw.tsv").writeText(tsv(raw))
                if (pp != null) File(out, "$name.pp.tsv").writeText(tsv(NemotronDiarizer.binarize(frame, pp)))
                fun save(suffix: String, f: NemotronFrameLogits) =
                    ByteBuffer.allocate(f.logits.size * 4).order(ByteOrder.LITTLE_ENDIAN).also { it.asFloatBuffer().put(f.logits) }
                        .array().let { File(out, "$name.$suffix.f32").writeBytes(it) }
                val passes = System.getProperty("c2pp.passes", "").split(',').filter { it.isNotBlank() }
                var extra = ""
                if (!saved && "warm" in passes) {
                    val audio = wav.inputStream().use { PcmWav.read(it) }
                    val t1 = System.nanoTime()
                    val warm = NemotronDiarizer.warmFrameLogits(audio.samples, filters, hann, silence, runner)
                    check(warm.frames == frame.frames)
                    save("warm", warm); extra += " warm_ms=${(System.nanoTime() - t1) / 1_000_000}"
                }
                if (!saved && "rev" in passes) {
                    val audio = wav.inputStream().use { PcmWav.read(it) }
                    val t1 = System.nanoTime()
                    val rev = NemotronDiarizer.frameLogits(audio.samples.reversedArray(), filters, hann, silence, runner)
                    // Back to forward time: frame t of the reversed pass covers forward frame frames-1-t.
                    val flipped = FloatArray(rev.logits.size)
                    for (t in 0 until rev.frames) System.arraycopy(rev.logits, t * 8, flipped, (rev.frames - 1 - t) * 8, 8)
                    save("rev", NemotronFrameLogits(flipped, rev.frames)); extra += " rev_ms=${(System.nanoTime() - t1) / 1_000_000} rev_frames=${rev.frames}"
                }
                println("$name frames=${frame.frames} c2_ms=$ms raw_turns=${raw.size} legacy=EQUAL$extra")
            }
        }
    }
}

/** Verbatim decision logic of the pre-post-processing NemotronDiarizer (main @ 66e9f31). */
private fun legacy(frame: NemotronFrameLogits): List<ClusterTurn> {
    val speakers = frame.speakers
    val opened = IntArray(speakers) { -1 }
    val turns = mutableListOf<ClusterTurn>()
    var written = 0
    for (row in 0 until frame.frames) {
        for (s in 0 until speakers) {
            val active = frame.logits[row * speakers + s] > 0f
            if (active && opened[s] < 0) opened[s] = written
            if (!active && opened[s] >= 0) {
                turns += ClusterTurn(opened[s] * 0.01f, written * 0.01f, s)
                opened[s] = -1
            }
        }
        written++
    }
    for (s in 0 until speakers) if (opened[s] >= 0) turns += ClusterTurn(opened[s] * 0.01f, written * 0.01f, s)
    return turns.sortedWith(compareBy<ClusterTurn> { it.startSeconds }.thenBy { it.cluster })
}
