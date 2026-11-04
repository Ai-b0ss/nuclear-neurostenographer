// SPDX-License-Identifier: LicenseRef-OpenMDW-1.1
package ru.neurostenographer.core

import java.io.Closeable

/** Calls the pinned ONNX Runtime C API from C++, without its Java JNI bridge. */
internal object NativeNemotronSession {
    init { System.loadLibrary("nemotron_native") }
    external fun create(modelPath: String, threads: Int): Long
    external fun destroy(handle: Long)
    external fun run(handle: Long, mel: FloatArray, melFrames: Int, melLength: Int,
                     context: FloatArray, contextFrames: Int): NemotronStep
}

class CppNemotronSession(modelPath: String, threads: Int) : Closeable {
    private var handle = NativeNemotronSession.create(modelPath, threads)
    fun run(mel: FloatArray, melFrames: Int, melLength: Int, context: FloatArray,
            contextFrames: Int): NemotronStep = NativeNemotronSession.run(
        handle, mel, melFrames, melLength, context, contextFrames)
    override fun close() {
        if (handle != 0L) NativeNemotronSession.destroy(handle)
        handle = 0L
    }
}
