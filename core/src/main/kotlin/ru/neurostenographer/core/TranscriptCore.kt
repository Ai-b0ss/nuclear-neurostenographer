package ru.neurostenographer.core

import kotlin.math.max
import kotlin.math.min
import java.util.Locale

/** All intervals are milliseconds from the beginning of the same recording. */
data class SpeakerTurn(val startMs: Long, val endMs: Long, val speakerId: String,
    val attributionEligible: Boolean = true) {
    init { require(startMs >= 0 && endMs > startMs && speakerId.isNotBlank()) }
}
data class RecognizedWord(val startMs: Long, val endMs: Long, val text: String) {
    init { require(startMs >= 0 && endMs > startMs && text.isNotBlank()) }
}
data class RecognizedChunk(val startMs: Long, val endMs: Long, val text: String) {
    init { require(startMs >= 0 && endMs > startMs && text.isNotBlank()) }
}
data class TranscriptSegment(
    val startMs: Long,
    val endMs: Long,
    val speakerId: String?,
    val text: String,
    val overlappingSpeech: Boolean = false,
    val attributionReliable: Boolean = false,
    /** Speakers whose turns overlap inside this fragment; [speakerId] stays null because the words cannot be
     * split between them. Shown as «Говорящий 1 + Говорящий 2» instead of «Не определён». */
    val overlapSpeakers: List<String> = emptyList()
) {
    init { require(startMs >= 0 && endMs > startMs && text.isNotBlank()) }
}

/** Words from a transducer's subword tokens and their emission times (sherpa-onnx
 * OfflineRecognizerResult.tokens / .timestamps: seconds from the window start, one per token,
 * start of the token, 40 ms frames for GigaAM). A token beginning with a space opens a word;
 * punctuation sticks to the previous word and does not move its timing. A word ends at the next
 * word's start or [TAIL_MS] after its last emitted token, whichever is first. Returns null when the
 * timing is missing or inconsistent, so the caller falls back to chunk attribution.
 */
object TokenWords {
    const val TAIL_MS = 240L
    private val PUNCT = Regex("[\\p{P}]+")

    fun words(tokens: Array<String>, seconds: FloatArray?, windowStartMs: Long, windowEndMs: Long): List<RecognizedWord>? {
        require(windowEndMs > windowStartMs)
        if (tokens.isEmpty()) return emptyList()
        if (seconds == null || seconds.size != tokens.size || seconds.any { !it.isFinite() || it < 0f }) return null
        if (seconds.toList().zipWithNext().any { (a, b) -> b < a }) return null
        class Draft(val startMs: Long, var lastMs: Long, val text: StringBuilder)
        val drafts = mutableListOf<Draft>()
        for (i in tokens.indices) {
            val token = tokens[i]
            val at = (windowStartMs + Math.round(seconds[i] * 1000.0)).coerceAtMost(windowEndMs - 1)
            val piece = token.trim()
            val last = drafts.lastOrNull()
            when {
                piece.isEmpty() -> if (last == null || last.text.isNotEmpty()) drafts += Draft(at, at, StringBuilder())
                PUNCT.matches(piece) && drafts.any { it.text.isNotEmpty() } ->
                    drafts.last { it.text.isNotEmpty() }.text.append(piece)
                last == null || (token.first().isWhitespace() && last.text.isNotEmpty()) ->
                    drafts += Draft(at, at, StringBuilder(piece))
                else -> { last.text.append(piece); last.lastMs = at }
            }
        }
        val kept = drafts.filter { it.text.isNotBlank() }
        return kept.mapIndexed { i, d ->
            val limit = kept.getOrNull(i + 1)?.startMs ?: windowEndMs
            val end = minOf(limit, d.lastMs + TAIL_MS, windowEndMs).coerceAtLeast(d.startMs + 1)
            RecognizedWord(d.startMs, end, d.text.toString())
        }
    }
}

/** Does not invent speaker IDs or word timestamps when evidence is ambiguous. */
object TranscriptFusion {
    private data class Attribution(val speakerId: String?, val overlap: Boolean, val reliable: Boolean,
                                   val overlapSpeakers: List<String> = emptyList())

    /** "Speaker 2" before "Speaker 10"; other ids alphabetically. */
    internal val SPEAKER_ORDER: Comparator<String> = compareBy<String>(
        { it.removePrefix("Speaker ").toIntOrNull() ?: Int.MAX_VALUE }, { it })

    fun attributeWords(
        words: List<RecognizedWord>,
        turns: List<SpeakerTurn>,
        minDominance: Double = 0.55,
        minMargin: Double = 0.25,
        maxGapMs: Long = 650
    ): List<TranscriptSegment> {
        require(minDominance in 0.0..1.0 && minMargin in 0.0..1.0 && maxGapMs >= 0)
        val input = words.sortedWith(compareBy<RecognizedWord> { it.startMs }.thenBy { it.endMs })
        val result = mutableListOf<TranscriptSegment>()
        for (word in input) {
            val a = attribute(word.startMs, word.endMs, turns, minDominance, minMargin)
            val current = TranscriptSegment(word.startMs, word.endMs, a.speakerId, word.text, a.overlap, a.reliable,
                a.overlapSpeakers)
            val previous = result.lastOrNull()
            if (previous != null && previous.speakerId == current.speakerId &&
                previous.overlappingSpeech == current.overlappingSpeech &&
                previous.overlapSpeakers == current.overlapSpeakers &&
                previous.attributionReliable == current.attributionReliable &&
                current.startMs <= previous.endMs + maxGapMs) {
                val noSpace = current.text.first() in ".,!?;:…»)" || previous.text.last() in "(«"
                result[result.lastIndex] = previous.copy(
                    endMs = max(previous.endMs, current.endMs),
                    text = previous.text + (if (noSpace) "" else " ") + current.text
                )
            } else result.add(current)
        }
        return result
    }

    /** Conservative fallback for ASR without word-level timestamps. */
    fun attributeChunks(chunks: List<RecognizedChunk>, turns: List<SpeakerTurn>): List<TranscriptSegment> =
        chunks.sortedBy { it.startMs }.map { c ->
            val a = attribute(c.startMs, c.endMs, turns, 0.9, 0.8)
            TranscriptSegment(c.startMs, c.endMs, a.speakerId, c.text, a.overlap, a.reliable, a.overlapSpeakers)
        }

    /** Joins adjacent fragments of one reliably attributed speaker into a reply.
     * Uncertain and overlapping fragments stay separate so their flags survive.
     */
    fun mergeReplies(segments: List<TranscriptSegment>, maxGapMs: Long = 1500,
                     maxDurationMs: Long = 60_000): List<TranscriptSegment> {
        val result = mutableListOf<TranscriptSegment>()
        for (current in segments) {
            val previous = result.lastOrNull()
            if (previous != null && previous.speakerId != null && previous.speakerId == current.speakerId &&
                previous.attributionReliable && current.attributionReliable &&
                !previous.overlappingSpeech && !current.overlappingSpeech &&
                current.startMs - previous.endMs <= maxGapMs &&
                current.endMs - previous.startMs <= maxDurationMs) {
                result[result.lastIndex] = previous.copy(endMs = max(previous.endMs, current.endMs),
                    text = previous.text + " " + current.text)
            } else result.add(current)
        }
        return result
    }

    private fun normalize(spans: List<Pair<Long, Long>>): List<Pair<Long, Long>> {
        val ordered = spans.sortedBy { it.first }
        val output = mutableListOf<Pair<Long, Long>>()
        for ((s, e) in ordered) {
            val previous = output.lastOrNull()
            if (previous != null && s <= previous.second)
                output[output.lastIndex] = previous.first to max(previous.second, e)
            else output.add(s to e)
        }
        return output
    }

    private fun total(spans: List<Pair<Long, Long>>): Long =
        normalize(spans).sumOf { it.second - it.first }

    private fun intersection(a: List<Pair<Long, Long>>, b: List<Pair<Long, Long>>): Long {
        var sum = 0L
        val aa = normalize(a)
        val bb = normalize(b)
        var i = 0
        var j = 0
        while (i < aa.size && j < bb.size) {
            sum += max(0L, min(aa[i].second, bb[j].second) - max(aa[i].first, bb[j].first))
            if (aa[i].second < bb[j].second) i++ else j++
        }
        return sum
    }

    private fun attribute(
        start: Long, end: Long, turns: List<SpeakerTurn>,
        minDominance: Double, minMargin: Double
    ): Attribution {
        val clips = turns.mapNotNull { turn ->
            val s = max(start, turn.startMs)
            val e = min(end, turn.endMs)
            if (e > s) turn.speakerId to (s to e) else null
        }
        if (clips.isEmpty()) return Attribution(null, false, false)
        val grouped = clips.groupBy({ it.first }, { it.second })
        val ranked = grouped.mapValues { total(it.value) }
            .toList().sortedWith(compareByDescending<Pair<String, Long>> { it.second }.thenBy { it.first })
        val groups = grouped.keys.toList()
        val overlapping = sortedSetOf(SPEAKER_ORDER)
        for (i in groups.indices) for (j in (i + 1) until groups.size)
            if (intersection(grouped.getValue(groups[i]), grouped.getValue(groups[j])) > 0L) {
                overlapping += groups[i]; overlapping += groups[j]
            }
        val overlap = overlapping.isNotEmpty()
        val duration = (end - start).toDouble()
        val second = ranked.getOrNull(1)?.second ?: 0L
        val uncertain = turns.any { !it.attributionEligible && it.startMs < end && it.endMs > start }
        val reliable = !overlap && !uncertain && ranked[0].second / duration >= minDominance &&
            (ranked[0].second - second) / duration >= minMargin
        return Attribution(if (reliable) ranked[0].first else null, overlap, reliable, overlapping.toList())
    }
}

data class TranscriptProvenance(val engine: String, val modelRevision: String,
    val timestampSource: String, val speakerSource: String, val runtimeSha256: String? = null) {
    init { require(runtimeSha256 == null || runtimeSha256.matches(Regex("[0-9a-f]{64}"))) }
}

/** One immutable inference result. No source URI/name or private path in exports. */
data class TranscriptDocument(val segments: List<TranscriptSegment>, val audioMs: Long,
    val provenance: TranscriptProvenance, val warnings: List<String> = emptyList()) {
    init {
        require(audioMs > 0 && segments.all { it.endMs <= audioMs })
        require(segments.zipWithNext().all { (a, b) -> a.startMs <= b.startMs })
    }
    /** [speakerNames] maps a stable id ("Speaker N") to a name the user typed; TXT/SRT show it, JSON adds `speaker_name`.
     * [termEdits] are accepted B0 spelling edits (TermDictionary): TXT/SRT show the edited text, JSON keeps the raw ASR
     * `text` and adds `text_edited` to the segments that changed. */
    fun export(format: String, speakerNames: Map<String, String> = emptyMap(), termEdits: List<TermEdit> = emptyList()): String {
        val edited = TermDictionary.apply(segments, termEdits)
        return when (format) {
            "json" -> TranscriptExport.json(segments, provenance, audioMs, warnings, speakerNames, edited)
            "json-contest" -> TranscriptExport.contestJson(segments)
            "srt" -> TranscriptExport.srt(edited, speakerNames)
            "txt" -> TranscriptExport.header(segments, audioMs) + "\n" +
                warnings.joinToString("") { "Примечание: $it\n" } + "\n" + TranscriptExport.txt(edited, speakerNames)
            else -> error("Неизвестный формат экспорта")
        }
    }
}

object TranscriptExport {
    /** Official Nuclear IT Hack 2026 projection: only transcript, speaker_id, start_ms, end_ms, text.
     * Raw ASR text is never replaced by user-edited spelling or made-up words for scoring.
     * Unknown speaker is a non-personal "unknown" string because the slide requires a string;
     * this choice must be clarified with organizers before treating it as scored.
     */
    fun contestJson(items: List<TranscriptSegment>): String {
        val ids = linkedMapOf<String, String>()
        val lines = items.map { segment ->
            val speaker = segment.speakerId?.let { id ->
                ids.getOrPut(id) { "speaker_" + (ids.size + 1) }
            } ?: "unknown"
            "    {\"speaker_id\": " + jsonString(speaker) +
                ", \"start_ms\": " + segment.startMs +
                ", \"end_ms\": " + segment.endMs +
                ", \"text\": " + jsonString(segment.text) + "}"
        }
        return "{\n  \"transcript\": [\n" + lines.joinToString(",\n") + "\n  ]\n}\n"
    }
    fun time(ms: Long): String {
        require(ms >= 0)
        return String.format(Locale.ROOT, "%02d:%02d:%02d.%03d", ms / 3600000,
            (ms / 60000) % 60, (ms / 1000) % 60, ms % 1000)
    }
    private fun srtTime(ms: Long): String =
        time(ms).replace('.', ',')
    private fun jsonString(s: String): String = buildString {
        append('"')
        for (c in s) when (c) {
            '"' -> append("\\\"")
            '\\' -> append("\\\\")
            '\n' -> append("\\n")
            '\r' -> append("\\r")
            '\t' -> append("\\t")
            else -> if (c.code < 32) append("\\u%04x".format(c.code)) else append(c)
        }
        append('"')
    }
    private val AUDIO_EXTENSION = Regex("\\.(wav|mp3|m4a|ogg|opus|flac|aac|amr|3gp|webm|mp4)$", RegexOption.IGNORE_CASE)
    /** Export file name without extension: only a known audio extension is dropped, so the dot in
     * "Запись 5 нояб., 01:40" is not taken for one; characters unsafe in file names become "_". */
    fun fileBase(title: String): String =
        title.trim().replace(AUDIO_EXTENSION, "").replace(Regex("[^\\p{L}\\p{N} _-]+"), "_")
            .trim(' ', '_').ifBlank { "transcript" }
    /** Human-readable first line of the TXT export; technical provenance stays in JSON. */
    fun header(items: List<TranscriptSegment>, audioMs: Long): String {
        val s = audioMs / 1000
        val duration = if (s >= 3600) String.format(Locale.ROOT, "%d:%02d:%02d", s / 3600, s / 60 % 60, s % 60)
            else String.format(Locale.ROOT, "%02d:%02d", s / 60, s % 60)
        return "Стенограмма · $duration · говорящих: " + items.mapNotNull { it.speakerId }.distinct().size
    }
    fun txt(items: List<TranscriptSegment>, names: Map<String, String> = emptyMap()): String = items.joinToString("\n") {
        "[" + time(it.startMs) + "–" + time(it.endMs) + "] " +
            segmentSpeaker(it, names) + ": " + it.text +
            (if (it.overlappingSpeech) " [перекрытие речи]" else "")
    }
    /** Speaker label of a fragment: overlapped speech without one attributable speaker lists everyone who spoke
     * («Говорящий 1 + Говорящий 2»); the words are not split between them. */
    fun segmentSpeaker(s: TranscriptSegment, names: Map<String, String> = emptyMap()): String =
        if (s.speakerId == null && s.overlapSpeakers.isNotEmpty()) s.overlapSpeakers.joinToString(" + ") { displaySpeaker(it, names) }
        else displaySpeaker(s.speakerId, names)
    /** Human-readable label for TXT/SRT; JSON keeps the stable id ("Speaker N"). A user-given name wins. */
    fun displaySpeaker(id: String?, names: Map<String, String> = emptyMap()): String = when {
        id == null -> "Не определён"
        !names[id].isNullOrBlank() -> names.getValue(id).trim()
        id.startsWith("Speaker ") -> "Говорящий " + id.removePrefix("Speaker ")
        else -> id
    }
    fun srt(items: List<TranscriptSegment>, names: Map<String, String> = emptyMap()): String =
        items.sortedBy { it.startMs }.mapIndexed { i, s ->
            (i + 1).toString() + "\n" + srtTime(s.startMs) + " --> " +
                srtTime(s.endMs) + "\n" + segmentSpeaker(s, names) + ": " + s.text +
                (if (s.overlappingSpeech) " [перекрытие речи]" else "")
        }.joinToString("\n\n")
    fun json(items: List<TranscriptSegment>, provenance: TranscriptProvenance? = null,
             audioMs: Long? = null, warnings: List<String> = emptyList(),
             names: Map<String, String> = emptyMap(), edited: List<TranscriptSegment> = items): String =
        "{\n  \"version\": 1,\n  \"units\": \"milliseconds\",\n" +
            (audioMs?.let { "  \"audio_duration_ms\": $it,\n" } ?: "") +
            "  \"warnings\": [" + warnings.joinToString(", ", transform = ::jsonString) + "],\n" +
            (provenance?.let { "  \"provenance\": {\"engine\": " + jsonString(it.engine) +
                ", \"model_revision\": " + jsonString(it.modelRevision) +
                ", \"timestamp_source\": " + jsonString(it.timestampSource) +
                ", \"speaker_source\": " + jsonString(it.speakerSource) +
                (it.runtimeSha256?.let { sha -> ", \"runtime_sha256\": " + jsonString(sha) } ?: "") + "},\n" } ?: "") +
            "  \"segments\": [\n" +
            items.withIndex().joinToString(",\n") { (index, it) ->
                val fixed = edited.getOrNull(index)?.text?.takeIf { t -> t != it.text }
                "    {\"start_ms\": " + it.startMs + ", \"end_ms\": " + it.endMs +
                    ", \"speaker_id\": " + (it.speakerId?.let(::jsonString) ?: "null") +
                    (it.speakerId?.let { id -> names[id]?.trim()?.takeIf(String::isNotEmpty) }
                        ?.let { name -> ", \"speaker_name\": " + jsonString(name) } ?: "") +
                    (if (it.overlapSpeakers.isEmpty()) "" else ", \"overlap_speaker_ids\": [" +
                        it.overlapSpeakers.joinToString(", ", transform = ::jsonString) + "]") +
                    ", \"text\": " + jsonString(it.text) + (fixed?.let { t -> ", \"text_edited\": " + jsonString(t) } ?: "") +
                    ", \"overlapping_speech\": " +
                    it.overlappingSpeech + ", \"attribution_reliable\": " + it.attributionReliable + "}"
            } + "\n  ]\n}\n"
}
