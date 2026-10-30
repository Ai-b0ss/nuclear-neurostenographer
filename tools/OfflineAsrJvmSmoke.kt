package ru.neurostenographer.tools

import ru.neurostenographer.app.OfflineAsr
import ru.neurostenographer.core.PcmAudio
import ru.neurostenographer.core.PcmWav
import ru.neurostenographer.core.TranscriptExport
import java.io.File

/** Supplemental host JNI evidence; never label this as an Android/device test. */
fun main(args: Array<String>) {
    require(args.size == 3) { "model-directory input.wav evidence.json" }
    // Windows dependency search does not consistently use java.library.path for dependent DLLs.
    if (System.getProperty("os.name").startsWith("Windows")) {
        System.load(File(System.getProperty("java.library.path"), "onnxruntime.dll").absolutePath)
    }
    val model = File(args[0])
    val audio = File(args[1]).inputStream().use { PcmWav.read(it) }
    val results = (1..2).map { run ->
        val result = OfflineAsr.transcribe(audio, model)
        val text = result.segments.joinToString(" ") { it.text }
        check(Regex("[а-яА-Я]{3,}").containsMatchIn(text)) { "No Russian recognized" }
        check(text.contains("у лукоморья дуб зеленый")) { "Known fixture phrase missing" }
        check(result.segments.all { it.speakerId == null && !it.attributionReliable && it.endMs <= audio.durationMs })
        println("HOST_JNI run=$run audio_ms=${result.audioMs} load_ms=${result.loadMs} decode_ms=${result.decodeMs} text=$text")
        result
    }
    check(results[0].segments == results[1].segments) { "Non-deterministic repeated ASR" }
    val silent = OfflineAsr.transcribe(PcmAudio(FloatArray(32000), 16000), model)
    check(silent.segments.isEmpty()) { "Silence hallucination: ${silent.segments}" }
    check(silent.decodedWindows > 0) // ASR actually ran but returned no text.
    val noSpeech = OfflineAsr.transcribe(audio, File(model, "does-not-exist"), speechWindows = emptyList())
    check(noSpeech.decodedWindows == 0 && noSpeech.segments.isEmpty() && noSpeech.loadMs == 0L)
    val shortTail = OfflineAsr.transcribe(PcmAudio(FloatArray(20 * 16000 + 160), 16000), model)
    check(shortTail.segments.isEmpty()) { "Silent short tail hallucinated" }
    try {
        OfflineAsr.transcribe(PcmAudio(FloatArray(1), 16000), model)
        error("Tiny input accepted")
    } catch (_: IllegalArgumentException) { }
    var checkpoints = 0
    try {
        OfflineAsr.transcribe(audio, model, { if (++checkpoints == 2) throw java.util.concurrent.CancellationException() })
        error("Cancellation ignored")
    } catch (_: java.util.concurrent.CancellationException) { }
    check(OfflineAsr.transcribe(PcmAudio(FloatArray(32000), 16000), model).segments.isEmpty())
    val runs = results.joinToString(",") { "{\"audio_ms\":${it.audioMs},\"load_ms\":${it.loadMs},\"decode_ms\":${it.decodeMs}}" }
    File(args[2]).writeText("{\"platform\":\"Host JNI; OS/architecture in summary.json; Android NOT_RUN\",\"runs\":[$runs]," +
        "\"repetition_pass\":true,\"silence_pass\":true,\"short_tail_pass\":true,\"cancellation_cleanup_pass\":true," +
        "\"transcript\":" + TranscriptExport.json(results.first().segments) + "}")
    println("PASS HOST_JNI repeated ASR, attribution, silence, short tail, tiny input, cancellation cleanup. Android NOT_RUN.")
}
