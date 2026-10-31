package ru.neurostenographer.core

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.file.Files
import java.security.MessageDigest
import java.util.concurrent.CancellationException
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

fun testVerifiedModelBundle() {
    val model = byteArrayOf(5, 10, 15)
    val token = byteArrayOf(1)
    fun pin(bytes: ByteArray) = PinnedArtifact(MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(it) }, bytes.size.toLong())
    val verifier = VerifiedModelBundle(mapOf("model.onnx" to pin(model), "tokens.txt" to pin(token)))
    fun zip(vararg entries: Pair<String, ByteArray>): ByteArray = ByteArrayOutputStream().also { out ->
        ZipOutputStream(out).use { z -> entries.forEach { (name, bytes) ->
            z.putNextEntry(ZipEntry(name)); z.write(bytes); z.closeEntry()
        } }
    }.toByteArray()
    fun staging(block: (File) -> Unit) {
        val dir = Files.createTempDirectory("model-import-test").toFile()
        try { block(dir) } finally { dir.listFiles()?.forEach { check(it.delete()) }; check(dir.delete()) }
    }
    val valid = zip("model.onnx" to model, "tokens.txt" to token)
    staging { dir ->
        verifier.unpack(ByteArrayInputStream(valid), dir)
        check(File(dir, "model.onnx").readBytes().contentEquals(model))
        verifier.verify(dir)
        File(dir, "tokens.txt").writeBytes(byteArrayOf(2))
        try { verifier.verify(dir); error("Tampering accepted") } catch (_: IllegalArgumentException) { }
    }
    for (bytes in listOf(
        zip("../escape.onnx" to model), zip("/absolute" to model),
        zip("model.onnx" to model), zip("model.onnx" to byteArrayOf(1, 2, 3), "tokens.txt" to token),
        zip("model.onnx" to ByteArray(10000), "tokens.txt" to token),
        zip("model.onnx" to model, "tokens.txt" to token, "extra" to token),
        valid.copyOf(20)
    )) staging { dir ->
        var rejected = false
        try { verifier.unpack(ByteArrayInputStream(bytes), dir) } catch (_: Exception) { rejected = true }
        check(rejected) { "Invalid model bundle accepted" }
    }
    staging { dir ->
        try { verifier.unpack(ByteArrayInputStream(valid), dir) { throw CancellationException() }; error("Cancellation ignored") }
        catch (_: CancellationException) { }
        check(dir.listFiles()!!.isEmpty())
    }
    println("PASS model ZIP: success, traversal, missing/extra files, bad hash, oversize, truncation, tampering, cancellation")
}
