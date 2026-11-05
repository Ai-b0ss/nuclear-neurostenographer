package ru.neurostenographer.tools

import ru.neurostenographer.app.*
import ru.neurostenographer.core.*
import java.io.File
import com.k2fsa.sherpa.onnx.*

/** Research-only entry point, actual app OfflineAsr and NemotronDiarization.
 * Same C2 intervals and app window/fusion policies on mixture and each stem.
 * QuietCuts uses the current waveform: this is disclosed, not fixed-window parity.
 */
fun main(args: Array<String>) {
    fun cpuMs(): Long = try { Class.forName("android.os.Process").getMethod("getElapsedCpuTime").invoke(null) as Long } catch(_: Exception) {-1L}
    val processCpuStart=cpuMs()
    if(System.getProperty("os.name").startsWith("Windows"))
        System.load(File(System.getProperty("java.library.path"), "onnxruntime.dll").absolutePath)
    else System.loadLibrary("onnxruntime")
    val audio = File(args[2]).inputStream().use { PcmWav.read(it) }
    if (args[0] == "c2") {
        val r = NemotronDiarization.process(audio, File(args[1]))
        File(args[3]).writeText(r.turns.joinToString("") {
            "${it.startMs}\t${it.endMs}\t${if(it.speakerId == "Unknown") -1 else it.speakerId.removePrefix("Speaker ").toInt()-1}\n"
        })
        File(args[4]).writeText("{\"load_ms\":${r.loadMs},\"infer_ms\":${r.processMs},\"process_cpu_ms\":${cpuMs()-processCpuStart},\"threads\":${InferenceThreads.count()}}")
    } else {
        val raw = File(args[3]).readLines().filter { it.isNotBlank() }.map {
            val (a,b,c) = it.split('\t'); ClusterTurn(a.toLong()/1000f,b.toLong()/1000f,c.toInt())
        }
        val turns = DiarizationTimeline.canonicalize(raw,audio.durationMs)
        val windows = DiarizationTimeline.speechWindows(raw,audio.durationMs)
        val r = OfflineAsr.transcribe(audio,File(args[1]),turns=turns,speechWindows=windows)
        File(args[4]).writeText(TranscriptExport.json(r.segments, audioMs=audio.durationMs))
        File(args[5]).writeText("{\"load_ms\":${r.loadMs},\"decode_ms\":${r.decodeMs},\"windows\":${r.decodedWindows},"+
            "\"token_timed_windows\":${r.tokenTimedWindows},\"untimed_windows\":${r.untimedWindows},\"process_cpu_ms\":${cpuMs()-processCpuStart},\"threads\":${InferenceThreads.count()}}")
        // Additional unmerged emission words for overlap-only research splicing.
        // A second deterministic decode; the app output above is independently retained.
        if(System.getProperty("research.words") != "false") {
        val recognizer=OfflineRecognizer(config=OfflineRecognizerConfig(
            featConfig=FeatureConfig(sampleRate=16000,featureDim=64),
            modelConfig=OfflineAsr.modelConfig(AsrModelSpec.ACTIVE,File(args[1])),decodingMethod="greedy_search"))
        val wordSegments=mutableListOf<TranscriptSegment>()
        try {
            for (w in QuietCuts.refine(windows,audio.samples)) {
                val stream=recognizer.createStream()
                try {
                    val x=audio.samples.copyOfRange((w.startMs*16).toInt(),minOf((w.endMs*16).toInt(),audio.samples.size))
                    stream.acceptWaveform(if(x.size<16000)x.copyOf(16000)else x,16000)
                    recognizer.decode(stream)
                    val result=recognizer.getResult(stream)
                    val words=TokenWords.words(result.tokens,result.timestamps,w.startMs,w.endMs)
                    if(words!=null && words.isNotEmpty()) for(word in words)
                        wordSegments+=TranscriptFusion.attributeWords(listOf(word),turns)
                    else if(result.text.isNotBlank()) wordSegments+=TranscriptFusion.attributeChunks(
                        listOf(RecognizedChunk(w.startMs,w.endMs,result.text.trim())),turns)
                } finally {stream.release()}
            }
        } finally {recognizer.release()}
        File(args[4]+".words.json").writeText(TranscriptExport.json(wordSegments.sortedBy{it.startMs},audioMs=audio.durationMs))
        }
    }
}
