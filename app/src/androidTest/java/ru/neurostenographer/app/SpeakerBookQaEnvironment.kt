package ru.neurostenographer.app

import android.os.Build
import androidx.test.platform.app.InstrumentationRegistry

/** Explicit emulator-only route. Physical tests keep every existing thermal guard. */
object SpeakerBookQaEnvironment {
    fun emulator(): Boolean {
        val requested = InstrumentationRegistry.getArguments().getString("qaEnvironment") ?: "physical"
        check(requested == "physical" || requested == "emulator") { "Unknown QA environment" }
        if (requested == "physical") return false
        check(BuildConfig.GLOBAL_SPEAKER_BOOK) { "Requires isolated speakerbook QA build" }
        check(Build.SUPPORTED_ABIS.contains("x86_64") &&
            Build.HARDWARE in setOf("ranchu", "goldfish")) {
            "Emulator thermal bypass is forbidden on physical hardware"
        }
        return true
    }

    fun timeout(milliseconds: Long): Long = if (emulator()) milliseconds * 4 else milliseconds
    fun label(): String = if (emulator()) "ANDROID_X86_64_EMULATOR_NOT_PHONE" else "PHYSICAL_ANDROID"
}
