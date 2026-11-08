package ru.neurostenographer.core

import java.io.File
import java.io.InputStream

data class AudioSnapshot(val file: File, val durationMs: Long)

/** Snapshot document-provider bytes before accepting a new input. The provider may
 * revoke access or change its contents later. Caller owns successful snapshots.
 */
object AudioSnapshots {
    const val MAX_BYTES = PcmFileAudio.MAX_ENCODED_BYTES

    fun import(input: InputStream, directory: File, checkCancelled: () -> Unit = {}): AudioSnapshot =
        importBounded(input, directory, MAX_BYTES, checkCancelled)

    internal fun importBounded(input: InputStream, directory: File, maxBytes: Long,
                               checkCancelled: () -> Unit = {}): AudioSnapshot {
        require(maxBytes in 1..MAX_BYTES)
        check(directory.isDirectory || directory.mkdirs())
        val stage = File.createTempFile("input-", ".wav", directory)
        var accepted = false
        try {
            stage.outputStream().buffered().use { output ->
                val buffer = ByteArray(64 * 1024)
                var total = 0L
                while (true) {
                    checkCancelled()
                    val count = input.read(buffer)
                    if (count < 0) break
                    require(count > 0) { "Источник WAV не возвращает данные" }
                    total += count
                    require(total <= maxBytes) { "Аудиофайл слишком большой (максимум 5 ГБ)" }
                    output.write(buffer, 0, count)
                }
            }
            val audio = PcmFileAudio(stage, checkCancelled)
            checkCancelled()
            accepted = true
            return AudioSnapshot(stage, audio.durationMs)
        } finally { if (!accepted) stage.delete() }
    }
}
