package ru.neurostenographer.app

/** Debug-only VAD experiment; its model is never part of the product APK. */
object NativeVadProbe {
    init { System.loadLibrary("nemotron_native") }
    external fun detect(wave: FloatArray, modelPath: String, threshold: Float): LongArray
}
