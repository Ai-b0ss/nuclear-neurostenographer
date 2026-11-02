package ru.neurostenographer.tools

import ru.neurostenographer.app.NemotronDiarization
import ru.neurostenographer.core.*
import java.io.File

/** Host check of the Kotlin port on the same ONNX Runtime 1.17.1 as the app: in.wav out.tsv, repeated in one JVM. */
fun main(args: Array<String>) {
    val model = File(args[0])
    for (line in File(args[1]).readLines().filter { it.isNotBlank() }) {
        val (wav, tsv, meta) = line.split('\t')
        val audio = File(wav).inputStream().use { PcmWav.read(it) }
        val result = NemotronDiarization.process(audio, model)
        File(tsv).writeText(result.turns.joinToString("") {
            val cluster = if (it.speakerId == "Unknown") -1 else it.speakerId.removePrefix("Speaker ").toInt() - 1
            "${it.startMs}\t${it.endMs}\t$cluster\n"
        })
        File(meta).writeText("{\"load_ms\":${result.loadMs},\"infer_ms\":${result.processMs},\"threads\":2,\"onnxruntime\":\"1.17.1\"}\n")
        println("$wav ${result.processMs}")
    }
}
