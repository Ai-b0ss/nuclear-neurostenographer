// SPDX-License-Identifier: LicenseRef-OpenMDW-1.1
package ru.neurostenographer.core

/** Uses the original float arrays without copying a complete recording into native memory. */
internal object NativeNemotronMel {
    init { System.loadLibrary("nemotron_native") }
    external fun write(
        wave: FloatArray, filters: FloatArray, hann: FloatArray,
        first: Int, count: Int, output: FloatArray
    )
}
