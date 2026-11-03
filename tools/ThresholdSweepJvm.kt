package ru.neurostenographer.tools

import ru.neurostenographer.app.OfflineDiarization
import ru.neurostenographer.core.*
import java.io.File

/** Host-only measurement: run the production diarization on many WAV files at several clustering
 * thresholds and write one JSON line per (file, threshold). Never Android evidence.
 * args: model-directory thresholds(comma) output.jsonl wav-directory
 */
fun main(args: Array<String>) {
    require(args.size == 4) { "model-directory thresholds output.jsonl wav-directory" }
    if (System.getProperty("os.name").startsWith("Windows"))
        System.load(File(System.getProperty("java.library.path"), "onnxruntime.dll").absolutePath)
    val model = File(args[0])
    val thresholds = args[1].split(",").map { it.trim().toFloat() }
    val out = File(args[2])
    val files = File(args[3]).listFiles { f -> f.name.endsWith(".wav") }!!.sortedBy { it.name }
    out.writeText("")
    for (file in files) {
        val audio = file.inputStream().use { PcmWav.read(it) }
        for (threshold in thresholds) {
            val result = OfflineDiarization.process(audio, model, clusteringThreshold = threshold)
            val turns = result.turns.joinToString(",", "[", "]") {
                "{\"start_ms\":${it.startMs},\"end_ms\":${it.endMs},\"speaker_id\":" +
                    (if (it.attributionEligible) "\"${it.speakerId}\"" else "null") + "}"
            }
            out.appendText("{\"file\":\"${file.name}\",\"threshold\":$threshold,\"process_ms\":${result.processMs},\"turns\":$turns}\n")
            println("${file.name} $threshold ${result.turns.count { it.attributionEligible }} turns, ${result.processMs} ms")
        }
    }
}
