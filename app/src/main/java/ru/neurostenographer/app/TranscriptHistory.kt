package ru.neurostenographer.app

import org.json.JSONObject
import ru.neurostenographer.core.TranscriptDocument
import ru.neurostenographer.core.TranscriptProvenance
import ru.neurostenographer.core.TranscriptSegment
import java.io.File

data class SavedTranscript(val id: String, val title: String, val createdMs: Long, val document: TranscriptDocument,
                           val speakerNames: Map<String, String> = emptyMap()) {
    val speakers: List<String> get() = document.segments.mapNotNull { it.speakerId }.distinct()
}

/** Finished transcripts kept in the app's private storage, so a restart does not lose them.
 * Each one is the same JSON as the export (`<id>.json`) plus a small `<id>.meta.json` (title, time and
 * `speaker_names`: stable id "Speaker N" → name the user typed; the inference JSON itself never changes).
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

    fun delete(id: String) {
        require(id.matches(Regex("t\\d+")))
        File(dir, "$id.json").delete(); File(dir, "$id.meta.json").delete()
    }

    fun deleteAll() { dir.listFiles().orEmpty().forEach { it.delete() } }

    private fun load(id: String): SavedTranscript {
        val meta = JSONObject(File(dir, "$id.meta.json").readText())
        val names = meta.optJSONObject("speaker_names")?.let { o -> o.keys().asSequence().associateWith { o.getString(it) } }.orEmpty()
        return SavedTranscript(id, meta.getString("title"), meta.getLong("created_ms"), parse(File(dir, "$id.json").readText()), names)
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
