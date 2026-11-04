// SPDX-License-Identifier: LicenseRef-OpenMDW-1.1
package ru.neurostenographer.core

/** Temporary JNI result carrier while native model and cache interfaces are unified. */
class NemotronStep(val logits: FloatArray, val logitFrames: Int,
                   val embeds: FloatArray, val embedFrames: Int)
