// SPDX-License-Identifier: LicenseRef-OpenMDW-1.1
package ru.neurostenographer.core

/** Fixed export constants; the provisioning script checks them against the pinned constants.npz. */
object NemotronConfig {
    const val HIDDEN = 512
    const val SPEAKERS = 8
    const val SUBSAMPLING = 8
    const val CHUNK = 340
    const val RIGHT_CONTEXT = 40
    const val FIFO = 40
    const val UPDATE_PERIOD = 300
    const val CACHE = 264
    const val SILENCE_FRAMES = 1
    const val SCORE_THRESHOLD = 0.25f
    const val LATEST_BOOST = 0.05f
    const val MIN_POSITIVE_RATE = 0.5
    const val STRONG_RATE = 0.75
    const val WEAK_RATE = 1.5
    const val HOP = 160
    const val N_FFT = 512
    const val WIN = 400
    const val MELS = 128
    const val BINS = 257
    const val PREEMPHASIS = 0.97f
    val LOG_GUARD = Math.scalb(1f, -24)
}

