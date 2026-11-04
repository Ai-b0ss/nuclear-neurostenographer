package ru.neurostenographer.app

/** Local C++ C API parity probe. No product code calls this entry point. */
object NativeAsrProbe {
    init { System.loadLibrary("nemotron_native") }
    external fun recognize(samples: FloatArray, modelDir: String, threads: Int): String
}
