package ru.neurostenographer.core

import java.io.File
import java.io.InputStream

data class AudioSnapshot(val file: File, val durationMs: Long)

/** Snapshot document-provider bytes before accepting a new input. The provider may
 * revoke access or change its contents later. Caller owns successful snapshots.
 */
object AudioSnapshots {
    const val MAX_BYTES = 48_000L * 4 * PcmWav.MAX_SECONDS + 1_048_576 + 8

    fun import(input: InputStream, directory: File, checkCancelled: () -> Unit = {}): AudioSnapshot {
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
                    require(total <= MAX_BYTES) { "WAV слишком большой (максимум 120 секунд)" }
                    output.write(buffer, 0, count)
                }
            }
            val audio = stage.inputStream().use { PcmWav.read(it, checkCancelled) }
            require(audio.durationMs in 100..PcmWav.MAX_SECONDS * 1000L) { "Нужен WAV длительностью 0,1–120 секунд" }
            checkCancelled()
            accepted = true
            return AudioSnapshot(stage, audio.durationMs)
        } finally { if (!accepted) stage.delete() }
    }
}
