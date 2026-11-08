package ru.neurostenographer.app

import android.content.Context
import android.util.Log
import ru.neurostenographer.core.*
import java.io.File
import java.security.MessageDigest

/** Optional second pass after A3 and Nemotron. Retain original text for failed regions. */
object FddtHybrid {
    private const val TAG = "FddtHybrid"
    private const val MODEL_ID = "fddt_e2e_rnnt_int8_hybrid_r1"
    private val models = linkedMapOf(
        "encoder_fddt.int8.onnx" to "98d9a0480416e61434b1edbca18491fcb0593ad27eb6e628cf687011c4921140",
        "decoder.onnx" to "75d61a4e5b1bfeaa667360bef042f284c43ca0a4e310de5de3377e6b48ac7835",
        "joint.onnx" to "8f007db342af76c7355912ab0611d66aaafa4d74df035ca0016ed622e4344fc7",
        "tokens.txt" to "39abae20e692998290c574e606f11a9edef2902a1995463fcff63d1490cf22b7"
    )

    fun transcribe(
        context: Context,
        audio: PcmAudio,
        turns: List<SpeakerTurn>,
        base: AsrOutput,
        checkCancelled: () -> Unit,
        onProgress: (Int, Int) -> Unit
    ): AsrOutput {
        val regions = FddtOverlapPlan.regions(turns, audio.durationMs)
        if (regions.isEmpty()) {
            Log.i(TAG, "No qualifying overlapped speaker turns; A3 preserved")
            return base.copy(segments = TranscriptFusion.mergeReplies(base.segments))
        }
        checkCancelled()
        val prepared = ensureModels(context,checkCancelled)
        Log.i(TAG, "Prepared " + regions.size + " overlap regions; ONNX CPU")
        val original = base.segments.toMutableList()
        var accepted = 0; var rejected = 0; var calls = 0
        val started = System.nanoTime()
        FddtOnnxRecognizer(prepared, InferenceThreads.count()).use { model ->
            for ((index, region) in regions.withIndex()) {
                checkCancelled()
                onProgress(index+1, regions.size)
                val candidates = mutableMapOf<String,String>()
                for (speaker in region.speakers) {
                    checkCancelled()
                    val a = (region.startMs - 2000L).coerceAtLeast(0L)
                    val b = (region.endMs + 2000L).coerceAtMost(audio.durationMs)
                    var samples = audio.samples.copyOfRange((a*16).toInt(), (b*16).toInt())
                    if (samples.size < 16000) samples = samples.copyOf(16000)
                    val mask = FddtOverlapPlan.mask(turns,speaker,a,samples.size)
                    val pieces = model.decode(samples, mask, FddtOverlapPlan.frameCount(samples.size),
                        Runnable { checkCancelled() })
                        .filter { t ->
                            val at = a + t.timeMs
                            at >= region.startMs-200L && at <= region.endMs+200L
                        }.map { it.piece }
                    calls++
                    candidates[speaker] = FddtOverlapPlan.decodePieces(pieces).trimStart(',', '.', '-', ' ')
                }
                val baseInRegion = original.filter {
                    val middle = it.startMs + (it.endMs - it.startMs)/2L
                    middle >= region.startMs && middle < region.endMs
                }
                val wordCount = baseInRegion.sumOf { it.text.split(Regex("\\s+")).count(String::isNotBlank) }
                if (!FddtOverlapPlan.canReplace(wordCount,candidates,region.speakers)) {
                    rejected++
                    Log.i(TAG,"region "+index+" fallback=A3 words="+wordCount+" FDDT="+
                        candidates.mapValues { it.value.split(Regex("\\s+")).count(String::isNotBlank) })
                    continue
                }
                original.removeAll(baseInRegion.toSet())
                for (speaker in region.speakers) {
                    val spans = turns.filter { it.speakerId == speaker && it.startMs < region.endMs
                        && it.endMs > region.startMs }
                    val s = spans.minOfOrNull { maxOf(region.startMs,it.startMs) } ?: region.startMs
                    val e = spans.maxOfOrNull { minOf(region.endMs,it.endMs) } ?: region.endMs
                    val text = candidates.getValue(speaker).trim()
                    if (text.isNotEmpty() && e > s) original += TranscriptSegment(
                        startMs=s,endMs=e,speakerId=speaker,text=text,
                        overlappingSpeech=true,attributionReliable=false,
                        overlapSpeakers=region.speakers)
                }
                accepted++
            }
        }
        val elapsed = (System.nanoTime()-started)/1_000_000
        Log.i(TAG,"Complete regions="+accepted+" accepted/"+rejected+" fallback, "+
            "ONNX_calls="+calls+", compute_ms="+elapsed+", audio_ms="+audio.durationMs)
        return base.copy(
            segments=TranscriptFusion.mergeReplies(original.sortedWith(
                compareBy<TranscriptSegment> { it.startMs }.thenBy { it.speakerId ?: "" })),
            decodeMs=base.decodeMs+elapsed,
            untimedWindows=base.untimedWindows+accepted,
            modelRevision= if (accepted>0) base.modelRevision+"+"+MODEL_ID else base.modelRevision
        )
    }

    private fun ensureModels(context: Context, checkCancelled: () -> Unit): File {
        val dir = File(context.filesDir,"fddt-rnnt-hybrid-r1").apply { mkdirs() }
        for ((name,hash) in models) {
            checkCancelled()
            val file = File(dir,name)
            val marker = File(dir,name+".sha256")
            if (file.isFile && file.length()>0 && marker.isFile && marker.readText() == hash) continue
            val temp = File(dir,name+".partial")
            temp.delete()
            try {
                val digest = MessageDigest.getInstance("SHA-256")
                context.assets.open(name).buffered().use { input ->
                    temp.outputStream().buffered().use { output ->
                        val buffer = ByteArray(65536)
                        while (true) {
                            checkCancelled()
                            val n = input.read(buffer)
                            if (n < 0) break
                            digest.update(buffer,0,n)
                            output.write(buffer,0,n)
                        }
                    }
                }
                val actual=digest.digest().joinToString("") { "%02x".format(it) }
                require(actual==hash) { "FDDT model checksum failed: $name" }
                if (file.exists()) file.delete()
                require(temp.renameTo(file)) { "Cannot install FDDT model $name" }
                marker.writeText(hash)
            } finally { temp.delete() }
        }
        return dir
    }
}
