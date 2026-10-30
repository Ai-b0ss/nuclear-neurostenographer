package ru.neurostenographer.app

import android.content.Context
import java.io.File
import java.io.InputStream
import ru.neurostenographer.core.PinnedArtifact
import ru.neurostenographer.core.VerifiedModelBundle

class DiarizationModelStore(context: Context) {
    private val root = File(context.filesDir, "diarization-models").apply { mkdirs() }
    private val preferences = context.getSharedPreferences("diarization-model", Context.MODE_PRIVATE)
    private val bundle = VerifiedModelBundle(ARTIFACTS)
    fun current(): File? = preferences.getString("active", null)?.let { name ->
        File(root, name).takeIf { it.isDirectory && it.parentFile == root }
    }
    fun verify(dir: File, checkCancelled: () -> Unit = {}) = bundle.verify(dir, checkCancelled)
    fun install(input: InputStream, checkCancelled: () -> Unit = {}): File {
        val stage = File.createTempFile("speakers-", ".stage", root)
        check(stage.delete() && stage.mkdir())
        var installed = false
        try {
            bundle.unpack(input, stage, checkCancelled)
            checkCancelled()
            val previous = current()
            check(preferences.edit().putString("active", stage.name).commit())
            installed = true
            previous?.let(::discard)
            return stage
        } finally { if (!installed) discard(stage) }
    }
    private fun discard(dir: File) {
        ARTIFACTS.keys.forEach { File(dir, it).delete() }
        dir.delete()
    }
    companion object {
        const val REVISION = "pyannote-9403a690/eres2net-1a331345/threshold-0.9"
        val ARTIFACTS = linkedMapOf(
            "segmentation.onnx" to PinnedArtifact("220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079", 5_992_913),
            "embedding.onnx" to PinnedArtifact("1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b", 39_593_761),
            "segmentation-LICENSE" to PinnedArtifact("14d7016ad68e7394d6e6b78d96cc2ae431c905287b89674cfdf021e79e62b8ba", 1061),
            "embedding-LICENSE" to PinnedArtifact("c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4", 11357)
        )
    }
}
