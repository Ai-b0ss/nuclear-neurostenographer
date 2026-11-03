package ru.neurostenographer.app

import android.os.Debug
import android.util.Log
import androidx.test.platform.app.InstrumentationRegistry
import com.google.ai.edge.litert.Accelerator
import com.google.ai.edge.litert.CompiledModel
import com.google.ai.edge.litert.Environment
import com.google.ai.edge.litert.TensorBuffer
import com.nemotron3diar.Engine
import com.nemotron3diar.MelFrontend
import com.nemotron3diar.Nemotron3Diarizer
import com.nemotron3diar.StreamConfig
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Test
import ru.neurostenographer.core.PcmWav
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread

/** Comparison probe for the LiteRT path, CPU accelerator (an emulator offers no OpenCL GPU).
 * Runs in the instrumentation process, not in :diarization: it decides between runtimes and is not a product path.
 */
class LiteRtProbeTest {
    private class Graph(val model: CompiledModel, inputs: List<String>, outputs: List<String>) {
        val ins: Map<String, TensorBuffer> = inputs.associateWith { model.createInputBuffer(it) }
        val outs: Map<String, TensorBuffer> = outputs.associateWith { model.createOutputBuffer(it) }
    }

    private class CpuEngine(env: Environment, dir: File) : Engine {
        private val options = CompiledModel.Options(Accelerator.CPU)
        private val a = Graph(CompiledModel.create(File(dir, "nemotron3_diar_frontend.tflite").absolutePath, options, env), listOf("mel"), listOf("chunk_embeds"))
        private val b = Graph(CompiledModel.create(File(dir, "nemotron3_diar_encoder_offline_fp16.tflite").absolutePath, options, env),
            listOf("packed_embeds", "attn_bias", "rope_cos", "rope_sin"), listOf("logits"))

        override fun frontend(mel: FloatArray): FloatArray {
            a.ins.getValue("mel").writeFloat(mel)
            a.model.run(a.ins, a.outs)
            return a.outs.getValue("chunk_embeds").readFloat()
        }

        override fun encoder(packed: FloatArray, bias: FloatArray, cos: FloatArray, sin: FloatArray): FloatArray {
            b.ins.getValue("packed_embeds").writeFloat(packed)
            b.ins.getValue("attn_bias").writeFloat(bias)
            b.ins.getValue("rope_cos").writeFloat(cos)
            b.ins.getValue("rope_sin").writeFloat(sin)
            b.model.run(b.ins, b.outs)
            return b.outs.getValue("logits").readFloat()
        }

        override fun close() {
            a.model.close()
            b.model.close()
        }
    }

    @Test fun offlineFileMode() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val assets = instrumentation.context.assets
        val dir = File(context.filesDir, "litert").apply { mkdirs() }
        for (name in assets.list("litert").orEmpty()) assets.open("litert/$name").use { input -> File(dir, name).outputStream().use { input.copyTo(it) } }
        fun floats(name: String): FloatArray {
            val bytes = File(dir, name).readBytes()
            return FloatArray(bytes.size / 4).also { ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(it) }
        }
        val runs = JSONArray()
        val out = File(context.filesDir, "litert-evidence.json")
        val plan = assets.open("nemotron-bench/plan.tsv").bufferedReader().readLines().filter { it.isNotBlank() }.map { it.split('\t')[0] }
        val env = Environment.create()
        val compileStarted = System.nanoTime()
        val engine = CpuEngine(env, dir)
        val compileMs = (System.nanoTime() - compileStarted) / 1_000_000
        for (id in plan) {
            val audio = assets.open("nemotron-bench/$id.wav").use { PcmWav.read(it) }
            val sampling = AtomicBoolean(true)
            var peak = 0
            val sampler = thread {
                while (sampling.get()) {
                    peak = maxOf(peak, Debug.MemoryInfo().also(Debug::getMemoryInfo).totalPss)
                    Thread.sleep(250)
                }
            }
            val evidence = JSONObject().put("case", id).put("audio_ms", audio.durationMs).put("backend", "litert_cpu_fp16")
            val started = System.nanoTime()
            try {
                val diarizer = Nemotron3Diarizer(engine, MelFrontend(floats("frontend_mel128_257.bin"), floats("hann400.bin")), floats("silence_embeds.bin"), StreamConfig.OFFLINE)
                val steps = diarizer.runFile(audio.samples)
                val frames = steps.sumOf { it.numFrames }
                val logits = FloatArray(frames * Nemotron3Diarizer.NUM_SPEAKERS)
                var at = 0
                for (step in steps) { step.logits.copyInto(logits, at); at += step.logits.size }
                val turns = Nemotron3Diarizer.segments(logits, frames)
                val limit = audio.durationMs
                evidence.put("status", "OK").put("turns", JSONArray(turns.map { JSONArray().put(it[0] * 10L).put(minOf(it[1] * 10L, limit)).put(it[2]) }))
            } catch (e: Throwable) {
                evidence.put("status", "FAIL").put("error", e.javaClass.simpleName + ": " + e.message)
            }
            evidence.put("infer_ms", (System.nanoTime() - started) / 1_000_000).put("compile_ms_once", compileMs)
            sampling.set(false)
            sampler.join()
            evidence.put("peak_process_pss_kib", peak)
            runs.put(evidence)
            out.writeText(JSONObject().put("runs", runs).toString())
            Log.i("NemotronBench", "$id litert ${evidence.getString("status")} ${evidence.getLong("infer_ms")} ms peak $peak KiB")
        }
        engine.close()
    }
}
