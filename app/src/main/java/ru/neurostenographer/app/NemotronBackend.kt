package ru.neurostenographer.app

import ru.neurostenographer.core.PcmAudio
import java.io.File
import java.lang.reflect.InvocationTargetException

/** Reaches the C2 prototype only in builds made with -PnemotronPrototype=true. Other builds have no such class. */
object NemotronBackend {
    const val C0 = "c0"
    const val C2 = "c2"

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
