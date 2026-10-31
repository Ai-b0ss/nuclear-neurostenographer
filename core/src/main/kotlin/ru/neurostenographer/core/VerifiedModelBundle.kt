package ru.neurostenographer.core

import java.io.File
import java.io.InputStream
import java.security.MessageDigest
import java.util.zip.ZipInputStream

data class PinnedArtifact(val sha256: String, val maxBytes: Long)

/** Strict allowlist extraction into a caller-owned empty staging directory. */
class VerifiedModelBundle(private val artifacts: Map<String, PinnedArtifact>) {
    init {
        require(artifacts.isNotEmpty() && artifacts.all { (name, pin) ->
            name.matches(Regex("[A-Za-z0-9_.-]+")) && name != "." && name != ".." &&
                pin.sha256.matches(Regex("[0-9a-f]{64}")) && pin.maxBytes > 0
        })
    }

    fun unpack(input: InputStream, stage: File, checkCancelled: () -> Unit = {}) {
        require(stage.isDirectory && stage.list()?.isEmpty() == true)
        val seen = mutableSetOf<String>()
        ZipInputStream(input).use { zip ->
            while (true) {
                checkCancelled()
                val entry = zip.nextEntry ?: break
                require(!entry.isDirectory && entry.name in artifacts && seen.add(entry.name)) {
                    "Неожиданный или повторный файл в ZIP модели"
                }
                val pin = artifacts.getValue(entry.name)
                var total = 0L
                File(stage, entry.name).outputStream().use { output ->
                    val buffer = ByteArray(128 * 1024)
                    while (true) {
                        checkCancelled()
                        val n = zip.read(buffer)
                        if (n < 0) break
                        total += n
                        require(total <= pin.maxBytes) { "Файл модели слишком большой" }
                        output.write(buffer, 0, n)
                    }
                }
                zip.closeEntry()
            }
        }
        require(seen == artifacts.keys) { "Неполный ZIP модели" }
        verify(stage, checkCancelled)
    }

    fun verify(dir: File, checkCancelled: () -> Unit = {}) {
        for ((name, pin) in artifacts) {
            val file = File(dir, name)
            require(file.length() in 1..pin.maxBytes) { "Неверный размер: $name" }
            val digest = MessageDigest.getInstance("SHA-256")
            file.inputStream().use { input ->
                val buffer = ByteArray(128 * 1024)
                while (true) {
                    checkCancelled()
                    val n = input.read(buffer)
                    if (n < 0) break
                    digest.update(buffer, 0, n)
                }
            }
            require(digest.digest().joinToString("") { "%02x".format(it) } == pin.sha256) {
                "SHA-256 не совпадает: $name. Модель не загружена."
            }
        }
    }
}
