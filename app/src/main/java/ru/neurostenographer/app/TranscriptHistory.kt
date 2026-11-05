package ru.neurostenographer.app

import org.json.JSONArray
import org.json.JSONObject
import ru.neurostenographer.core.Term
import ru.neurostenographer.core.TermDictionary
import ru.neurostenographer.core.TermEdit
import ru.neurostenographer.core.TranscriptDocument
import ru.neurostenographer.core.TranscriptProvenance
import ru.neurostenographer.core.TranscriptSegment
import java.io.File

data class SavedTranscript(val id: String, val title: String, val createdMs: Long, val document: TranscriptDocument,
                           val speakerNames: Map<String, String> = emptyMap(),
                           val termEdits: List<TermEdit> = emptyList(), val dismissedTerms: Set<String> = emptySet()) {
    val speakers: List<String> get() = document.segments.mapNotNull { it.speakerId }.distinct()
    /** What the screen and TXT/SRT show: raw ASR plus the spelling edits the user accepted. */
    val shownSegments: List<TranscriptSegment> by lazy { TermDictionary.apply(document.segments, termEdits) }
}

/** Stable key of a proposal, so accepted and declined ones are not proposed again. */
fun TermEdit.key() = "$segment:$start:$original"

/** Finished transcripts kept in the app's private storage, so a restart does not lose them.
 * Each one is the same JSON as the export (`<id>.json`) plus a small `<id>.meta.json` (title, time and
 * `speaker_names`: stable id "Speaker N" → name the user typed; `term_edits`/`term_dismissed`: accepted and declined
 * spelling proposals of the term dictionary; the inference JSON itself never changes).
 * Writes go through a temporary file and a rename: a crash leaves either the old state or the new one.
 */
class TranscriptHistory(filesDir: File) {
    private val dir = File(filesDir, "transcripts").apply { mkdirs() }

    fun save(title: String, document: TranscriptDocument, createdMs: Long = System.currentTimeMillis()): SavedTranscript {
        val id = "t$createdMs"
        atomicWrite(File(dir, "$id.json"), document.export("json"))
        atomicWrite(File(dir, "$id.meta.json"), JSONObject().put("title", title).put("created_ms", createdMs).toString())
        return SavedTranscript(id, title, createdMs, document)
    }

    fun list(): List<SavedTranscript> = dir.listFiles { f -> f.name.matches(Regex("t\\d+\\.json")) }.orEmpty()
        .mapNotNull { file -> runCatching { load(file.name.removeSuffix(".json")) }.getOrNull() }
        .sortedByDescending { it.createdMs }

    fun rename(id: String, title: String) {
        val meta = JSONObject(File(dir, "$id.meta.json").readText())
        atomicWrite(File(dir, "$id.meta.json"), meta.put("title", title).toString())
    }

    /** A blank [name] removes the name, so the label falls back to "Говорящий N". */
    fun setSpeakerName(id: String, speakerId: String, name: String) {
        val meta = JSONObject(File(dir, "$id.meta.json").readText())
        val names = meta.optJSONObject("speaker_names") ?: JSONObject()
        if (name.isBlank()) names.remove(speakerId) else names.put(speakerId, name)
        atomicWrite(File(dir, "$id.meta.json"), meta.put("speaker_names", names).toString())
    }

    /** Accepted edits are added, declined proposals remembered; [reset] drops both (back to the raw ASR text). */
    fun setTermEdits(id: String, accepted: List<TermEdit>, declined: List<TermEdit>, reset: Boolean = false) {
        val meta = JSONObject(File(dir, "$id.meta.json").readText())
        val edits = if (reset) JSONArray() else meta.optJSONArray("term_edits") ?: JSONArray()
        val dismissed = if (reset) JSONArray() else meta.optJSONArray("term_dismissed") ?: JSONArray()
        accepted.forEach { e -> edits.put(JSONObject().put("segment", e.segment).put("start", e.start).put("end", e.end)
            .put("original", e.original).put("replacement", e.replacement)) }
        declined.forEach { dismissed.put(it.key()) }
        atomicWrite(File(dir, "$id.meta.json"), meta.put("term_edits", edits).put("term_dismissed", dismissed).toString())
    }

    fun delete(id: String) {
        require(id.matches(Regex("t\\d+")))
        File(dir, "$id.json").delete(); File(dir, "$id.meta.json").delete()
    }

    fun deleteAll() { dir.listFiles().orEmpty().forEach { it.delete() } }

    private fun load(id: String): SavedTranscript {
        val meta = JSONObject(File(dir, "$id.meta.json").readText())
        val names = meta.optJSONObject("speaker_names")?.let { o -> o.keys().asSequence().associateWith { o.getString(it) } }.orEmpty()
        val edits = meta.optJSONArray("term_edits")?.let { a -> (0 until a.length()).map { i -> a.getJSONObject(i).let { e ->
            TermEdit(e.getInt("segment"), e.getInt("start"), e.getInt("end"), e.getString("original"), e.getString("replacement")) } } }.orEmpty()
        val dismissed = meta.optJSONArray("term_dismissed")?.let { a -> (0 until a.length()).map { a.getString(it) }.toSet() }.orEmpty()
        return SavedTranscript(id, meta.getString("title"), meta.getLong("created_ms"), parse(File(dir, "$id.json").readText()),
            names, edits, dismissed)
    }

    private fun atomicWrite(target: File, text: String) {
        val temp = File(target.parentFile, target.name + ".tmp")
        temp.writeText(text, Charsets.UTF_8)
        check(temp.renameTo(target) || (target.delete() && temp.renameTo(target))) { "Не удалось сохранить стенограмму" }
    }

    companion object {
        fun parse(json: String): TranscriptDocument {
            val root = JSONObject(json)
            val p = root.getJSONObject("provenance")
            val provenance = TranscriptProvenance(p.getString("engine"), p.getString("model_revision"),
                p.getString("timestamp_source"), p.getString("speaker_source"), p.optString("runtime_sha256").ifEmpty { null })
            val items = root.getJSONArray("segments")
            val segments = (0 until items.length()).map { i ->
                val s = items.getJSONObject(i)
                TranscriptSegment(s.getLong("start_ms"), s.getLong("end_ms"),
                    if (s.isNull("speaker_id")) null else s.getString("speaker_id"), s.getString("text"),
                    s.optBoolean("overlapping_speech"), s.optBoolean("attribution_reliable"))
            }
            val warnings = root.optJSONArray("warnings")?.let { w -> (0 until w.length()).map { w.getString(it) } }.orEmpty()
            return TranscriptDocument(segments, root.getLong("audio_duration_ms"), provenance, warnings)
        }
    }
}

/** Terms the user added («как распознано» → «как писать»), shared by all transcripts, kept in `terms.json`. */
class UserTerms(filesDir: File) {
    private val file = File(filesDir, "terms.json")

    fun list(): List<Term> = runCatching {
        val a = JSONArray(file.readText())
        (0 until a.length()).map { i -> a.getJSONObject(i).let { o ->
            Term(o.getString("canonical"), o.getJSONArray("variants").let { v -> (0 until v.length()).map(v::getString) }) } }
    }.getOrDefault(emptyList())

    fun add(heard: String, canonical: String): List<Term> {
        val variant = heard.trim().lowercase().replace(Regex("\\s+"), " ")
        val term = Term(canonical.trim(), listOf(variant))
        val all = list().filterNot { it.variants == term.variants } + term
        val out = JSONArray()
        all.forEach { t -> out.put(JSONObject().put("canonical", t.canonical).put("variants", JSONArray(t.variants))) }
        val temp = File(file.parentFile, file.name + ".tmp")
        temp.writeText(out.toString(), Charsets.UTF_8)
        check(temp.renameTo(file) || (file.delete() && temp.renameTo(file))) { "Не удалось сохранить словарь" }
        return all
    }
}
