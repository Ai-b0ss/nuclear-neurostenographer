package ru.neurostenographer.tools
import ai.onnxruntime.*
import ru.neurostenographer.core.*
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import java.lang.management.ManagementFactory
import com.sun.management.OperatingSystemMXBean

/** Same product C2 two-pass algorithm; only ORT thread-pool settings vary. */
fun main(args: Array<String>) {
    val model=File(args[0]);val wav=File(args[1]);val out=File(args[2]).apply { mkdirs() }
    fun floats(name:String):FloatArray {
        val bytes=File(model,name).readBytes()
        return FloatArray(bytes.size/4).also { ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(it) }
    }
    val filters=floats("mel_filters.bin");val hann=floats("hann400.bin");val silence=floats("silence_embeds.bin")
    val audio=wav.inputStream().use { PcmWav.read(it) }
    val cpu=ManagementFactory.getOperatingSystemMXBean() as OperatingSystemMXBean
    check(cpu.processCpuTime>=0)
    val env=OrtEnvironment.getEnvironment()
    val modes=listOf("four_spin","four_sleep","two_sleep")
    val rows=mutableListOf<String>();var reference:String?=null
    for (round in -1..2) {
        for (offset in modes.indices) {
            val mode=modes[(offset+maxOf(round,0))%modes.size]
            OrtSession.SessionOptions().use { options ->
                options.setIntraOpNumThreads(if(mode=="two_sleep") 2 else 4)
                if(mode=="four_spin") {
                    options.addConfigEntry("session.intra_op.allow_spinning","1")
                    options.addConfigEntry("session.inter_op.allow_spinning","1")
                } else BatchInferencePolicy.configure { key,value -> options.addConfigEntry(key,value) }
                env.createSession(File(model,"model.int8.ir9.onnx").absolutePath,options).use { session ->
                    val runner=NemotronChunkRunner { mel,frames,length,history,contextFrames ->
                        val inputs=linkedMapOf<String,OnnxTensor>()
                        try {
                            inputs["chunk_mel"]=OnnxTensor.createTensor(env,FloatBuffer.wrap(mel),longArrayOf(1,frames.toLong(),128))
                            inputs["chunk_mel_length"]=OnnxTensor.createTensor(env,length.toLong())
                            inputs["context_embeds"]=OnnxTensor.createTensor(env,FloatBuffer.wrap(history),longArrayOf(1,contextFrames.toLong(),512))
                            inputs["context_length"]=OnnxTensor.createTensor(env,contextFrames.toLong())
                            session.run(inputs).use { result ->
                                val l=result[0] as OnnxTensor;val e=result[1] as OnnxTensor
                                NemotronStep(FloatArray(l.floatBuffer.remaining()).also { l.floatBuffer.get(it) },l.info.shape[1].toInt(),
                                    FloatArray(e.floatBuffer.remaining()).also { e.floatBuffer.get(it) },e.info.shape[1].toInt())
                            }
                        } finally {inputs.values.forEach { it.close() }}
                    }
                    val c0=cpu.processCpuTime;val t0=System.nanoTime()
                    val turns=NemotronDiarizer.diarize(audio.samples,filters,hann,silence,runner,{},
                        NemotronPostprocess.PRODUCT,warmSecondPass=true)
                    val wall=(System.nanoTime()-t0)/1e6;val used=(cpu.processCpuTime-c0)/1e6
                    val text=turns.joinToString("") { "${Math.round(it.startSeconds*1000.0)}\t${Math.round(it.endSeconds*1000.0)}\t${it.cluster}\n" }
                    if(reference==null)reference=text
                    val equal=text==reference
                    File(out,mode+"-"+round+".tsv").writeText(text)
                    val idle0=cpu.processCpuTime;Thread.sleep(200);val idle=(cpu.processCpuTime-idle0)/1e6
                    if(round>=0)rows += """{"mode":"$mode","round":$round,"wall_ms":$wall,"cpu_ms":$used,"idle200_cpu_ms":$idle,"turns":${turns.size},"equal_ms_turns":$equal}"""
                    println("MEASURE $mode round=$round wall_ms=$wall cpu_ms=$used equal=$equal")
                }
            }
        }
    }
    File(out,"measurements.json").writeText("""{"schema":"c2-runtime-cpu-v1","scope":"HOST_NOT_PHONE","audio_ms":${audio.durationMs},"rows":[${rows.joinToString(",")}]}"""+"\n")
}
