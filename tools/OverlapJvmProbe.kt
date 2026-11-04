package ru.neurostenographer.tools

import ru.neurostenographer.app.OfflineDiarization
import ru.neurostenographer.core.*
import java.io.File

/** Run in a disposable child JVM: pinned native runtime has crashed on this input. */
fun main(args: Array<String>) {
    if (System.getProperty("os.name").startsWith("Windows"))
        System.load(File(System.getProperty("java.library.path"), "onnxruntime.dll").absolutePath)
    val audio = File(args[1]).inputStream().use { PcmWav.read(it) }
    val mixed = FloatArray(5 * 16000) { i -> (audio.samples[i + 16000] + audio.samples[i + 7 * 16000]) * 0.5f }
    val result = OfflineDiarization.process(PcmAudio(mixed, 16000), File(args[0]))
    val overlap = result.turns.indices.any { i -> result.turns.drop(i + 1).any { b ->
        val a = result.turns[i]
        a.speakerId != b.speakerId && minOf(a.endMs, b.endMs) > maxOf(a.startMs, b.startMs)
    } }
    File(args[2]).writeText("{\"native_completed\":true,\"known_mixture_overlap_detected\":$overlap,\"turn_count\":${result.turns.size}}\n")
}
