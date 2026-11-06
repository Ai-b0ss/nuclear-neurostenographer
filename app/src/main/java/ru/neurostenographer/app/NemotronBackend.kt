package ru.neurostenographer.app

import ru.neurostenographer.core.PcmAudio
import java.io.File
import java.io.InputStream
import java.lang.reflect.InvocationTargetException
import android.util.AtomicFile

/** Reaches the C2 prototype only in builds made with -PnemotronPrototype=true. Other builds have no such class. */
object NemotronBackend {
    const val C0 = "c0"
    const val C2 = "c2"

    const val REVISION = "nemotron3-diarization-onnx-4a911fc3/int8-ir9"

    fun current(filesDir: File): File? {
        if (!BuildConfig.NEMOTRON_PROTOTYPE) return null
        val root = File(filesDir, "nemotron-models")
        val pointer = AtomicFile(File(root, "active.txt"))
        val name = if (pointer.baseFile.exists() || File(root, "active.txt.bak").exists()) {
            runCatching { pointer.readFully().toString(Charsets.UTF_8) }.getOrNull() ?: return null
        } else "current" // compatibility with the existing signed product installation
        if (name != "current" && !name.matches(Regex("bundle-[0-9]+\\.stage"))) return null
        val dir = File(root, name)
        if (dir.canonicalFile.parentFile != root.canonicalFile) return null
        // A size check is only a quick readiness hint. The native call verifies all
        // pinned SHA-256 hashes again before trusting any model weights.
        return dir.takeIf { File(it, "model.int8.ir9.onnx").length() == 103_726_888L }
    }

    fun install(filesDir: File, source: InputStream): File {
        check(BuildConfig.NEMOTRON_PROTOTYPE) { "Nemotron C2 is unavailable in this build" }
        val type = Class.forName("ru.neurostenographer.app.NemotronDiarization")
        val method = type.getMethod("install", File::class.java, InputStream::class.java)
        return try {
            method.invoke(type.getField("INSTANCE").get(null), filesDir, source) as File
        } catch (e: InvocationTargetException) {
            throw e.targetException
        }
    }

    fun process(audio: PcmAudio, model: File, checkCancelled: () -> Unit): DiarizationOutput {
        check(BuildConfig.NEMOTRON_PROTOTYPE) { "Nemotron prototype is not in this build" }
        val type = Class.forName("ru.neurostenographer.app.NemotronDiarization")
        val method = type.getMethod("process", PcmAudio::class.java, File::class.java, Function0::class.java)
        try {
            return method.invoke(type.getField("INSTANCE").get(null), audio, model, checkCancelled) as DiarizationOutput
        } catch (e: InvocationTargetException) {
            throw e.targetException
        }
    }
}
