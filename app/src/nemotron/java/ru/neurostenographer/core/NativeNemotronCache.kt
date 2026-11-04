// SPDX-License-Identifier: LicenseRef-OpenMDW-1.1
package ru.neurostenographer.core

import java.io.Closeable

/** Per-recording C++ speaker cache; Java owns only the lifetime and ONNX call boundary. */
internal object NativeNemotronCache {
    init { System.loadLibrary("nemotron_native") }
    external fun create(silence: FloatArray): Long
    external fun destroy(handle: Long)
    external fun frames(handle: Long): Int
    external fun context(handle: Long): FloatArray
    external fun update(handle: Long, logits: FloatArray, logitFrames: Int,
                        embeds: FloatArray, embedFrames: Int, chunkFrames: Int)
}

class NativeNemotronSpeakerCache(silence: FloatArray) : Closeable {
    private var handle = NativeNemotronCache.create(silence)
    fun contextFrames(): Int = NativeNemotronCache.frames(handle)
    fun context(): FloatArray = NativeNemotronCache.context(handle)
    fun update(step: NemotronStep, chunkFrames: Int) = NativeNemotronCache.update(
        handle, step.logits, step.logitFrames, step.embeds, step.embedFrames, chunkFrames)
    override fun close() {
        if (handle != 0L) NativeNemotronCache.destroy(handle)
        handle = 0L
    }
}
