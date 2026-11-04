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
    private val bundle = VerifiedModelBundle(AsrModelSpec.ACTIVE.files.mapValues { (_, pin) -> PinnedArtifact(pin.first, pin.second) })

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
        val REVISION = AsrModelSpec.ACTIVE.revision
        val HASHES: Map<String, String> = AsrModelSpec.ACTIVE.files.mapValues { it.value.first }
    }
}
