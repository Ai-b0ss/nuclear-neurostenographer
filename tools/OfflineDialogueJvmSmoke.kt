package ru.neurostenographer.tools

import ru.neurostenographer.app.*
import ru.neurostenographer.core.*
import java.io.File

fun main(args: Array<String>) {
    require(args.size == 4) { "asr-model diarization-model russian.wav evidence.json" }
    if (System.getProperty("os.name").startsWith("Windows"))
        System.load(File(System.getProperty("java.library.path"), "onnxruntime.dll").absolutePath)
    val audio = File(args[2]).inputStream().use { PcmWav.read(it) }
    val diarization = validateWorkerReply(audio.durationMs, OfflineDiarization.process(audio, File(args[1])))
    check(diarization.turns.isNotEmpty())
    val result = OfflineAsr.transcribe(audio, File(args[0]), turns = diarization.turns, speechWindows = diarization.windows)
    check(result.segments.isNotEmpty())
    check(result.segments.any { Regex("[а-яА-Я]{3,}").containsMatchIn(it.text) })
    check(result.segments.all { it.endMs <= audio.durationMs })
    check(result.segments.any { it.speakerId != null && it.attributionReliable })
    check(result.segments.all { it.speakerId != null }) // clean single-voice fixture, silence gaps not decoded
    check(result.segments.any { it.text.contains("у лукоморья дуб зеленый") })
    val document = TranscriptDocument(result.segments, audio.durationMs, TranscriptProvenance(
        "Host JNI sherpa-onnx-1.12.20/gigaam-v3; OS/architecture in summary.json; Android NOT_RUN",
        "32a4c7cc81809bd132e2d935ab99e9e6ab47fbec",
        "diarization_boundaries_and_input_windows", "pyannote-9403a690/eres2net-1a331345/threshold-${OfflineDiarization.THRESHOLD}"),
        listOf("Chunk intervals from diarization/input windows; not word alignment."))
    val output = File(args[3])
    output.writeText(document.export("json"))
    for (format in listOf("txt", "srt")) output.resolveSibling("dialogue.$format").writeText(document.export(format))
    println("PASS HOST actual Russian ASR + diarization + fusion/export; single public voice, not conversational WER/DER")
    println("ASR load_ms=${result.loadMs} decode_ms=${result.decodeMs}; diarization load_ms=${diarization.loadMs} process_ms=${diarization.processMs}")
    println(TranscriptExport.txt(result.segments))
}
