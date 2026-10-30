package ru.neurostenographer.app

import android.content.Context
import java.io.File
import java.io.InputStream
import ru.neurostenographer.core.PinnedArtifact
import ru.neurostenographer.core.VerifiedModelBundle

/** A failed or cancelled import keeps the previous verified installation selected. */
class AsrModelStore(context: Context) {
    private val root = File(context.filesDir, "asr-models").apply { mkdirs() }
    private val preferences = context.getSharedPreferences("asr-model", Context.MODE_PRIVATE)
    private val bundle = VerifiedModelBundle(HASHES.mapValues { (name, hash) ->
        PinnedArtifact(hash, if (name == "model.int8.onnx") 224_721_476L else 4096L)
    })

    fun current(): File? = preferences.getString("active", null)?.let { name ->
        File(root, name).takeIf { it.isDirectory && it.parentFile == root }
    }

    fun verify(dir: File, checkCancelled: () -> Unit = {}) = bundle.verify(dir, checkCancelled)

    fun install(input: InputStream, checkCancelled: () -> Unit = {}): File {
        val stage = File.createTempFile("gigaam-", ".stage", root)
        check(stage.delete() && stage.mkdir())
        var installed = false
        try {
            bundle.unpack(input, stage, checkCancelled)
            checkCancelled()
            val previous = current()
            check(preferences.edit().putString("active", stage.name).commit()) { "Ошибка сохранения модели" }
            installed = true
            previous?.let(::discard)
            return stage
        } finally {
            if (!installed) discard(stage)
        }
    }

    private fun discard(dir: File) {
        HASHES.keys.forEach { File(dir, it).delete() }
        dir.delete()
    }

    companion object {
        const val REVISION = "32a4c7cc81809bd132e2d935ab99e9e6ab47fbec"
        val HASHES = linkedMapOf(
            "model.int8.onnx" to "f86ebfa0429ced91be6054fc344827e9c6c2572f3c318416cd974b06f66437ec",
            "tokens.txt" to "17cc514451bcceac9c280068c71502f8448f99e9fb1456b8d0761651fd0392f2",
            "LICENSE" to "f00de6715714c7a63d08639cdbfaa40224eefc407302614bd19f1a8b98c875aa"
        )
    }
}
