package ru.neurostenographer.tools

import ru.neurostenographer.core.*
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Writes the Kotlin log-mel as little-endian floats, for comparison with the ONNX preprocessor. */
fun main(args: Array<String>) {
    fun floats(path: File): FloatArray {
        val bytes = path.readBytes()
        return FloatArray(bytes.size / 4).also { ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(it) }
    }
    val model = File(args[0])
    val audio = File(args[1]).inputStream().use { PcmWav.read(it) }
    val mel = NemotronMel(audio.samples, floats(File(model, "mel_filters.bin")), floats(File(model, "hann400.bin")))
    val out = FloatArray(mel.frames * NemotronConfig.MELS)
    mel.write(0, mel.frames, out)
    val buffer = ByteBuffer.allocate(out.size * 4).order(ByteOrder.LITTLE_ENDIAN)
    buffer.asFloatBuffer().put(out)
    File(args[2]).writeBytes(buffer.array())
}
