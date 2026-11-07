package ru.neurostenographer.app

import android.content.Context
import ru.neurostenographer.core.PinnedArtifact
import ru.neurostenographer.core.VerifiedModelBundle
import java.io.File

/** Optional bundled English route, installed without network or a user model picker. */
object EnglishModelStore {
    const val ZIP = "whisper-tiny.zip"
    val PINS = linkedMapOf(
        "tiny-encoder.int8.onnx" to PinnedArtifact("d24fb083ae3b1041fc24e97971d60e280c9342201fbb67b0ab428a8b4a51a434", 12_937_772),
        "tiny-decoder.int8.onnx" to PinnedArtifact("d2fece8dd42771f1df975c6c0445770d0c292bf7547c2cae04a6c0cc57540925", 89_855_401),
        "tiny-tokens.txt" to PinnedArtifact("b34b360dbb493e781e479794586d661700670d65564001f23024971d1f2fa126", 816_730))

    @Synchronized fun ensure(context: Context, checkCancelled: () -> Unit = {}): File {
        val root = File(context.filesDir, "english-models").apply { check(isDirectory || mkdirs()) }
        val target = File(root, "whisper-tiny-65176e2")
        val bundle = VerifiedModelBundle(PINS)
        if (target.isDirectory) {
            bundle.verify(target, checkCancelled)
            return target
        }
        val stage = File.createTempFile("whisper-", ".stage", root)
        check(stage.delete() && stage.mkdir())
        try {
            context.assets.open(ZIP).use { bundle.unpack(it, stage, checkCancelled) }
            checkCancelled()
            check(stage.renameTo(target)) { "Не удалось сохранить английскую модель" }
            return target
        } finally {
            PINS.keys.forEach { File(stage, it).delete() }
            stage.delete()
        }
    }
}
