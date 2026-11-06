package ru.neurostenographer.core

import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest

/**
 * Atomically advertises a COMPLETE set of JSON/TXT/SRT exports.
 *
 * Each revision lives in a distinct immutable directory; readers MUST follow
 * transcript-current.json, not the three compatibility aliases at the root.
 * A crash before the pointer rename leaves the prior revision authoritative.
 * A crash afterwards leaves all referenced files available and verifiable.
 *
 * Only internally created snapshot names are managed. WAV/audio is never touched.
 * Fail closed if atomic pointer replacement isn't supported by the filesystem.
 */
class TranscriptSnapshotStore(
    private val directory: File,
    private val fault: (String) -> Unit = {}
) {
    data class Revision(
        val number: Long,
        val state: String,
        val audioMs: Long,
        val json: File,
        val txt: File,
        val srt: File
    )

    private val versions = File(directory, "transcript-versions")
    private val currentFile = File(directory, "transcript-current.json")
    private val versionName = Regex("v[0-9]{10}")
    private val pointerPattern = Regex(
        """\{"revision":([0-9]+),"state":"(PROVISIONAL|FINAL)","audio_ms":([0-9]+),"snapshot_sha256":"([0-9a-f]{64})"\}\n?"""
    )
    private val metaPattern = Regex(
        """\{"revision":([0-9]+),"state":"(PROVISIONAL|FINAL)","audio_ms":([0-9]+),"json_sha256":"([0-9a-f]{64})","txt_sha256":"([0-9a-f]{64})","srt_sha256":"([0-9a-f]{64})"\}\n?"""
    )
    private var nextRevision: Long

    init {
        require(directory.isDirectory) { "Realtime session directory must exist" }
        check(versions.isDirectory || versions.mkdir()) { "Cannot create transcript revision store" }
        // Interrupted staging directories also consume revision numbers.
        // Without this, a restarted publisher could collide with an orphan.
        val onDisk = Regex("""(?:\.pending-)?v[0-9]{10}""")
        val maxOnDisk = versions.listFiles().orEmpty().filter { it.isDirectory && onDisk.matches(it.name) }
            .maxOfOrNull { it.name.substringAfterLast("v").toLong() } ?: 0L
        val previous = current()?.number ?: 0L
        nextRevision = maxOf(maxOnDisk, previous) + 1L
    }

    @Synchronized
    fun publish(json: String, txt: String, srt: String, audioMs: Long, final: Boolean): Revision {
        require(audioMs >= 0L && audioMs <= 3_600_000L)
        check(nextRevision <= 9_999_999_999L) { "Revision sequence exhausted" }
        val revision = nextRevision++
        val state = if (final) "FINAL" else "PROVISIONAL"
        val base = "v" + revision.toString().padStart(10, '0')
        val pending = File(versions, ".pending-$base")
        val completed = File(versions, base)
        check(!pending.exists() && !completed.exists() && pending.mkdir()) { "Revision name collision" }
        val documents = listOf(
            Triple("transcript.json", json, "json"),
            Triple("transcript.txt", txt, "txt"),
            Triple("transcript.srt", srt, "srt")
        )
        val hashes = mutableMapOf<String, String>()
        for ((filename, body, key) in documents) {
            val target = File(pending, filename)
            writeDurable(target, body)
            hashes[key] = sha(target)
            fault("after-$key")
        }
        val manifestText = """{"revision":$revision,"state":"$state","audio_ms":$audioMs,"json_sha256":"${hashes.getValue("json")}","txt_sha256":"${hashes.getValue("txt")}","srt_sha256":"${hashes.getValue("srt")}"}""" + "\n"
        val manifest = File(pending, "snapshot.json")
        writeDurable(manifest, manifestText)
        fault("after-snapshot")
        check(pending.renameTo(completed)) { "Cannot publish immutable snapshot directory" }
        fault("after-directory")
        val pointer = """{"revision":$revision,"state":"$state","audio_ms":$audioMs,"snapshot_sha256":"${sha(File(completed, "snapshot.json"))}"}""" + "\n"
        atomicWrite(currentFile, pointer)
        fault("after-pointer")

        // Legacy per-format files are best-effort compatibility mirrors.
        // During a crash they may be mixed; transcript-current.json is authoritative.
        for ((filename, body, key) in documents) {
            atomicWrite(File(directory, filename), body)
            fault("after-compat-$key")
        }
        // Retain at least two previous complete snapshots for crash diagnosis.
        pruneCommitted(revision)
        return Revision(revision, state, audioMs, File(completed, "transcript.json"),
            File(completed, "transcript.txt"), File(completed, "transcript.srt"))
    }

    @Synchronized
    fun current(): Revision? {
        if (!currentFile.exists()) return null
        val match = pointerPattern.matchEntire(currentFile.readText(StandardCharsets.UTF_8))
            ?: throw IOException("Invalid transcript-current.json pointer")
        val id = match.groupValues[1].toLong()
        val state = match.groupValues[2]
        val audioMs = match.groupValues[3].toLong()
        val folder = File(versions, "v" + id.toString().padStart(10, '0'))
        require(folder.parentFile == versions && versionName.matches(folder.name))
        val manifest = File(folder, "snapshot.json")
        if (!manifest.isFile || sha(manifest) != match.groupValues[4])
            throw IOException("Snapshot manifest missing or mismatched")
        val fields = metaPattern.matchEntire(manifest.readText(StandardCharsets.UTF_8))
            ?: throw IOException("Snapshot format invalid")
        if (fields.groupValues[1].toLong() != id || fields.groupValues[2] != state ||
            fields.groupValues[3].toLong() != audioMs)
            throw IOException("Snapshot and current pointer disagree")
        val names = listOf("transcript.json", "transcript.txt", "transcript.srt")
        for ((index, name) in names.withIndex()) {
            val path = File(folder, name)
            if (!path.isFile || sha(path) != fields.groupValues[4 + index])
                throw IOException("Corrupted transcript snapshot: $name")
        }
        return Revision(id, state, audioMs, File(folder, names[0]), File(folder, names[1]), File(folder, names[2]))
    }

    private fun pruneCommitted(committed: Long) {
        versions.listFiles().orEmpty()
            .filter { it.isDirectory && versionName.matches(it.name) }
            .filter { it.name.substring(1).toLong() < committed - 2L }
            .forEach { it.deleteRecursively() }
    }

    private fun atomicWrite(path: File, body: String) {
        val pending = File(path.parentFile, path.name + ".tmp")
        writeDurable(pending, body)
        Files.move(pending.toPath(), path.toPath(),
            StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
    }

    private fun writeDurable(path: File, body: String) {
        FileOutputStream(path).use { stream ->
            stream.write(body.toByteArray(StandardCharsets.UTF_8))
            stream.fd.sync()
        }
    }

    private fun sha(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(65536)
            while (true) {
                val size = input.read(buffer)
                if (size < 0) break
                digest.update(buffer, 0, size)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
