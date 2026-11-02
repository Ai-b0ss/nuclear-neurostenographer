package ru.neurostenographer.tools

import ru.neurostenographer.app.*
import ru.neurostenographer.core.*
import java.io.File

/** Host harness over the production Kotlin classes. One recording per JVM: pinned JNI may crash.
 *
 * c0 diarization-model in.wav turns.tsv meta.json
 * asr asr-model in.wav turns.tsv transcript.json meta.json
 * turns.tsv: start_ms, end_ms, cluster (-1 = unknown). The same ASR path receives C0 and C1 turns.
 */
fun main(args: Array<String>) {
    if (System.getProperty("os.name").startsWith("Windows"))
        System.load(File(System.getProperty("java.library.path"), "onnxruntime.dll").absolutePath)
    when (args.firstOrNull()) {
        "c0" -> {
            require(args.size in 5..6)
            val threshold = args.getOrNull(5)?.toFloat() ?: OfflineDiarization.THRESHOLD
            val audio = File(args[2]).inputStream().use { PcmWav.read(it) }
            val result = OfflineDiarization.process(audio, File(args[1]), clusteringThreshold = threshold)
            File(args[3]).writeText(result.turns.joinToString("") {
                val cluster = if (it.speakerId == "Unknown") -1 else it.speakerId.removePrefix("Speaker ").toInt() - 1
                "${it.startMs}\t${it.endMs}\t$cluster\n"
            })
            File(args[4]).writeText("{\"load_ms\":${result.loadMs},\"process_ms\":${result.processMs}," +
                "\"threshold\":$threshold,\"threads\":2}\n")
        }
        "asr" -> {
            require(args.size == 6)
            val audio = File(args[2]).inputStream().use { PcmWav.read(it) }
            val raw = File(args[3]).readLines().filter { it.isNotBlank() }.map { line ->
                val (start, end, cluster) = line.split('\t')
                ClusterTurn(start.toLong() / 1000f, end.toLong() / 1000f, cluster.toInt())
            }
            val turns = DiarizationTimeline.canonicalize(raw, audio.durationMs)
            val windows = DiarizationTimeline.speechWindows(raw, audio.durationMs)
            val result = OfflineAsr.transcribe(audio, File(args[1]), turns = turns, speechWindows = windows)
            File(args[4]).writeText(TranscriptExport.json(result.segments))
            File(args[5]).writeText("{\"load_ms\":${result.loadMs},\"decode_ms\":${result.decodeMs}," +
                "\"windows\":${result.decodedWindows},\"threads\":2}\n")
        }
        else -> error("Usage: c0|asr ...")
    }
}
