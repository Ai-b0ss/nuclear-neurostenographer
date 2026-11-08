package ru.neurostenographer.app

import android.content.Context
import android.util.Log
import ru.neurostenographer.core.*
import java.io.File
import java.security.MessageDigest

/** Optional second pass after A3 and Nemotron. Retain original text for failed regions. */
object FddtHybrid {
    private const val TAG = "FddtHybrid"
    private val MODEL_ID = if (BuildConfig.FDDT_WORD_RECOVERY) "fddt_e2e_rnnt_int8_hybrid_r3"
        else "fddt_e2e_rnnt_int8_attribution_r1"
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
        // Attribution preserves every baseline word, so longer speaker context
        // is useful without replacing clean speech. Recovery is separately opt-in.
        val regions = FddtOverlapPlan.regions(turns, audio.durationMs, wholeTurns = !BuildConfig.FDDT_WORD_RECOVERY)
            .filter { region -> BuildConfig.FDDT_WORD_RECOVERY || base.segments.any {
                it.speakerId == null && it.overlappingSpeech && it.text.isNotBlank() &&
                    it.startMs < region.endMs && it.endMs > region.startMs
            } }
        if (regions.isEmpty()) {
            Log.i(TAG, "No qualifying overlapped speaker turns; A3 preserved")
            return base.copy(segments = TranscriptFusion.mergeReplies(base.segments))
        }
        checkCancelled()
        val prepared = ensureModels(context,checkCancelled)
        Log.i(TAG, "Prepared " + regions.size + " overlap regions; ONNX CPU")
        val original = base.segments.toMutableList()
        val acceptedEvidence = mutableListOf<TranscriptSegment>()
        var accepted = 0; var rejected = 0; var calls = 0
        val started = System.nanoTime()
        FddtOnnxRecognizer(prepared, InferenceThreads.count()).use { model ->
            for ((index, region) in regions.withIndex()) {
                checkCancelled()
                onProgress(index+1, regions.size)
                val candidates = mutableMapOf<String,String>()
                val timed = mutableMapOf<String,List<RecognizedWord>>()
                // Keep every boundary-crossing A3 fragment intact. Without token
                // timing a partial chunk cannot safely be removed or split.
                val boundary = base.segments.filter { it.startMs < region.endMs && it.endMs > region.startMs &&
                    !(it.startMs >= region.startMs && it.endMs <= region.endMs) }
                if (boundary.any { it.text.trim().split(Regex("\\s+")).size > 1 }) {
                    rejected++
                    Log.i(TAG,"region "+index+" fallback=A3 boundary chunk")
                    continue
                }
                for (speaker in region.speakers) {
                    checkCancelled()
                    val a = (region.startMs - 2000L).coerceAtLeast(0L)
                    val b = (region.endMs + 2000L).coerceAtMost(audio.durationMs)
                    var samples = audio.samples.copyOfRange((a*16).toInt(), (b*16).toInt())
                    if (samples.size < 16000) samples = samples.copyOf(16000)
                    val mask = FddtOverlapPlan.mask(turns,speaker,a,samples.size)
                    val pieces = model.decode(samples, mask, FddtOverlapPlan.frameCount(samples.size),
                        Runnable { checkCancelled() })
                    val words = TokenWords.words(
                        pieces.map { it.piece.replace('\u2581',' ') }.toTypedArray(),
                        pieces.map { it.timeMs/1000f }.toFloatArray(), a, b).orEmpty()
                        .filter { word -> FddtOverlapPlan.owns(region,word) &&
                            turns.any { it.speakerId == speaker && word.startMs >= it.startMs-200L &&
                                word.startMs < it.endMs+200L } &&
                            boundary.none { old -> (old.speakerId == null || old.speakerId == speaker) &&
                                word.startMs < old.endMs && word.endMs > old.startMs } }
                    calls++
                    timed[speaker] = words
                    candidates[speaker] = words.joinToString(" ") { it.text }.trimStart(',', '.', '-', ' ')
                }
                val baseInRegion = original.filter {
                    it.startMs >= region.startMs && it.endMs <= region.endMs
                }
                val wordCount = baseInRegion.sumOf { it.text.split(Regex("\\s+")).count(String::isNotBlank) }
                if (!FddtOverlapPlan.canReplace(baseInRegion,candidates,region.speakers)) {
                    rejected++
                    Log.i(TAG,"region "+index+" fallback=A3 words="+wordCount+" FDDT="+
                        candidates.mapValues { it.value.split(Regex("\\s+")).count(String::isNotBlank) })
                    continue
                }
                original.removeAll(baseInRegion.toSet())
                for (speaker in region.speakers) {
                    // Keep emission-based word timing and pauses rather than assigning
                    // a whole merged region to a speaker who was active briefly.
                    val replies = mutableListOf<TranscriptSegment>()
                    for (word in timed.getValue(speaker)) {
                        val previous = replies.lastOrNull()
                        if (previous != null && word.startMs <= previous.endMs+650L) {
                            replies[replies.lastIndex] = previous.copy(endMs=maxOf(previous.endMs,word.endMs),
                                text=previous.text+" "+word.text)
                        } else replies += TranscriptSegment(word.startMs,word.endMs,speaker,word.text,
                            overlappingSpeech=true,attributionReliable=false,overlapSpeakers=region.speakers)
                    }
                    original += replies
                    // Attribution needs the time of the matching word, rather than
                    // the span of a multiword reply containing it somewhere.
                    acceptedEvidence += timed.getValue(speaker).map { word ->
                        TranscriptSegment(word.startMs,word.endMs,speaker,word.text,
                            overlappingSpeech=true,attributionReliable=false,overlapSpeakers=region.speakers)
                    }
                }
                accepted++
            }
        }
        val elapsed = (System.nanoTime()-started)/1_000_000
        Log.i(TAG,"Complete regions="+accepted+" accepted/"+rejected+" fallback, "+
            "ONNX_calls="+calls+", compute_ms="+elapsed+", audio_ms="+audio.durationMs)
        val refined = if (BuildConfig.FDDT_WORD_RECOVERY) original.sortedWith(
            compareBy<TranscriptSegment> { it.startMs }.thenBy { it.speakerId ?: "" })
            else FddtOverlapPlan.refineAttribution(base.segments,acceptedEvidence)
        val changed = if (BuildConfig.FDDT_WORD_RECOVERY) accepted > 0 else refined != base.segments
        return base.copy(
            segments=TranscriptFusion.mergeReplies(refined),
            decodeMs=base.decodeMs+elapsed,
            untimedWindows=base.untimedWindows+(if (BuildConfig.FDDT_WORD_RECOVERY) accepted else 0),
            modelRevision= if (changed) base.modelRevision+"+"+MODEL_ID else base.modelRevision
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
