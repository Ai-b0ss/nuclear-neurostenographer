package ru.neurostenographer.app

/** Candidate C++ owner of the sherpa ASR model/stream lifecycle. */
internal class NativeAsrSession private constructor(private var handle: Long) : AutoCloseable {
    companion object {
        fun open(modelDir: String, threads: Int): NativeAsrSession =
            NativeAsrSession(NativeAsrBridge.create(modelDir, threads))
    }

    fun recognize(samples: FloatArray): String {
        check(handle != 0L)
        return NativeAsrBridge.decode(handle, samples)
    }

    override fun close() {
        val owned = handle
        handle = 0L
        if (owned != 0L) NativeAsrBridge.destroy(owned)
    }
}

internal object NativeAsrBridge {
    init { System.loadLibrary("nemotron_native") }
    external fun run(samples: FloatArray, modelDir: String, threads: Int,
                     windows: LongArray, checkCancelled: () -> Unit,
                     progress: (Int, Int) -> Unit, timing: LongArray): Array<String>
    external fun create(modelDir: String, threads: Int): Long
    external fun decode(handle: Long, samples: FloatArray): String
    external fun destroy(handle: Long)
}
