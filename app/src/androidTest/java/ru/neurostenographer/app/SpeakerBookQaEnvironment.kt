package ru.neurostenographer.app

import android.os.Build
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.security.MessageDigest

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

    /** Let the app UID create the optional-model directory on scoped external storage. */
    fun prepareOptionalModel() {
        if (!emulator()) return
        val inst = InstrumentationRegistry.getInstrumentation()
        val qa = requireNotNull(inst.targetContext.getExternalFilesDir("qa"))
        val directory = File(qa, "titanet")
        check(directory.isDirectory || directory.mkdirs()) { "Cannot prepare QA TitaNet directory" }
        val output = File(directory, "nemo_en_titanet_small.onnx")
        val temporary = File(directory, "nemo_en_titanet_small.onnx.staging")
        val digest = MessageDigest.getInstance("SHA-256")
        try {
            inst.context.assets.open("speakerbook/nemo_en_titanet_small.onnx").use { input ->
                temporary.outputStream().use { target ->
                    val buffer = ByteArray(65536)
                    while (true) {
                        val count = input.read(buffer)
                        if (count < 0) break
                        digest.update(buffer, 0, count)
                        target.write(buffer, 0, count)
                    }
                }
            }
            check(digest.digest().joinToString("") { "%02x".format(it) } ==
                "ad4a1802485d8b34c722d2a9d04249662f2ece5d28a7a039063ca22f515a789e") {
                "Emulator TitaNet asset checksum mismatch"
            }
            check(!output.exists() || output.delete()) { "Cannot replace emulator QA model" }
            check(temporary.renameTo(output) && output.isFile && output.canRead()) {
                "Emulator QA model is not readable by target app"
            }
        } finally {
            temporary.delete()
        }
    }

    fun timeout(milliseconds: Long): Long = if (emulator()) milliseconds * 4 else milliseconds
    fun label(): String = if (emulator()) "ANDROID_X86_64_EMULATOR_NOT_PHONE" else "PHYSICAL_ANDROID"
}
