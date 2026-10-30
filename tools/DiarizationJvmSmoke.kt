package ru.neurostenographer.tools

import ru.neurostenographer.app.OfflineDiarization
import ru.neurostenographer.app.DiarizationOutput
import ru.neurostenographer.core.*
import java.io.File

/** Exercise the actual production IPC validation on real model output, without
 * pretending this host runs Android Binder or service lifecycle callbacks.
 */
internal fun validateWorkerReply(audioMs: Long, result: DiarizationOutput): DiarizationOutput {
    val checked = DiarizationReply.validate(audioMs,
        result.turns.map { it.startMs }.toLongArray(), result.turns.map { it.endMs }.toLongArray(),
        result.turns.map { it.speakerId }, result.turns.map { it.attributionEligible }.toBooleanArray(),
        result.windows.map { it.startMs }.toLongArray(), result.windows.map { it.endMs }.toLongArray(),
        result.loadMs, result.processMs)
    check(checked.turns == result.turns && checked.windows == result.windows)
    return result.copy(turns = checked.turns, windows = checked.windows)
}

/** Actual host native inference, never Android evidence or a DER benchmark. */
fun main(args: Array<String>) {
    require(args.size == 3) { "model-directory four-speakers.wav evidence.json" }
    if (System.getProperty("os.name").startsWith("Windows"))
        System.load(File(System.getProperty("java.library.path"), "onnxruntime.dll").absolutePath)
    val model = File(args[0])
    val audio = File(args[1]).inputStream().use { PcmWav.read(it) }
    val runs = (1..2).map {
        val result = validateWorkerReply(audio.durationMs, OfflineDiarization.process(audio, model))
        println("NATIVE load_ms=${result.loadMs} process_ms=${result.processMs} turns=${result.turns}")
        check(result.turns.isNotEmpty())
        check(result.turns.all { it.endMs <= audio.durationMs })
        fun at(ms: Long) = result.turns.filter { ms in it.startMs until it.endMs }.single().speakerId
        // Official upstream example: first voice recurs after another utterance.
        check(at(2000) == at(23000) && at(2000) != at(8000)) { "A-B-A recurrence failed" }
        result
    }
    check(runs[0].turns == runs[1].turns) { "Repeated labels/times changed" }
    val silence = OfflineDiarization.process(PcmAudio(FloatArray(32000), 16000), model)
    validateWorkerReply(2000, silence)
    check(silence.turns.isEmpty()) { "Speakers invented on silence" }
    // Same genuine voices, composed A -> B -> A, not a naturally recorded dialogue.
    val aba = audio.samples.copyOfRange(16000, 6 * 16000) + FloatArray(16000) +
        audio.samples.copyOfRange(7 * 16000, 10 * 16000) + FloatArray(16000) +
        audio.samples.copyOfRange(22 * 16000, 25 * 16000)
    val composed = OfflineDiarization.process(PcmAudio(aba, 16000), model)
    validateWorkerReply(aba.size * 1000L / 16000, composed)
    println("COMPOSED_ABA ${composed.turns}")
    fun label(ms: Long) = composed.turns.filter { ms in it.startMs until it.endMs }.single().speakerId
    check(label(2000) == label(11000) && label(2000) != label(7000))
    val short = OfflineDiarization.process(PcmAudio(audio.samples.copyOfRange(16000, 6 * 16000), 16000), model)
    validateWorkerReply(5000, short)
    check(short.turns.isNotEmpty() && short.turns.all { it.endMs <= 5000 })
    var checks = 0
    try {
        OfflineDiarization.process(PcmAudio(FloatArray(32000), 16000), model,
            { if (++checks == 3) throw java.util.concurrent.CancellationException() })
        error("Cancellation ignored")
    } catch (_: java.util.concurrent.CancellationException) { }
    check(OfflineDiarization.process(PcmAudio(FloatArray(32000), 16000), model).turns.isEmpty())
    fun turnsJson(turns: List<SpeakerTurn>) = turns.joinToString(",", "[", "]") {
        "{\"start_ms\":${it.startMs},\"end_ms\":${it.endMs},\"speaker_id\":\"${it.speakerId}\"}"
    }
    File(args[2]).writeText("{\"platform\":\"Host JNI; OS/architecture in summary.json; Android NOT_RUN\",\"threshold\":0.9," +
        "\"fixture\":\"Public upstream Chinese four-speaker example; not Russian DER benchmark\"," +
        "\"aba_pass\":true,\"repeat_pass\":true,\"silence_pass\":true,\"short_pass\":true,\"cancellation_cleanup_pass\":true,\"worker_reply_validation_pass\":true," +
        "\"runs\":" + runs.joinToString(",", "[", "]") { "{\"load_ms\":${it.loadMs},\"process_ms\":${it.processMs},\"turns\":${turnsJson(it.turns)}}" } +
        ",\"composed_aba_turns\":${turnsJson(composed.turns)}}\n")
    println("PASS actual host segmentation + embeddings + clustering, A-B-A and negatives. Android NOT_RUN")
}
