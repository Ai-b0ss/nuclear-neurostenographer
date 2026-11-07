package ru.neurostenographer.app

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Test
import org.junit.Assume.assumeTrue
import org.junit.runner.RunWith
import ru.neurostenographer.core.*
import java.io.File

@RunWith(AndroidJUnit4::class)
class EnglishCheckpointTest {
    @Test fun englishRussianAndSilence() {
        assumeTrue(BuildConfig.ENGLISH_AUTO && BuildConfig.APPLICATION_ID.endsWith(".checkpoint"))
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val model = EnglishModelStore.ensure(context)
        fun audio(name: String) = instrumentation.context.assets.open(name).use { PcmWav.read(it) }
        val english = audio("english.wav")
        val englishWindows = DiarizationTimeline.windows(emptyList(), english.durationMs)
        check(WhisperEnglish.detect(english, model, englishWindows) == "en")
        val result = WhisperEnglish.transcribe(english, model, emptyList(), null)
        val text = result.segments.joinToString(" ") { it.text }
        check(text.isNotBlank() && text.any { it in 'a'..'z' || it in 'A'..'Z' }) { text }
        check(result.segments.all { it.speakerId == null && it.endMs <= english.durationMs })
        for (name in listOf("russian.wav", "russian-aba.wav", "russian-acted.wav", "russian-syn4.wav")) {
            val russian = audio(name)
            check(WhisperEnglish.detect(russian, model,
                DiarizationTimeline.windows(emptyList(), russian.durationMs)) == "ru") { "Wrong language: $name" }
        }
        val silence = PcmAudio(FloatArray(16000), 16000)
        check(WhisperEnglish.detect(silence, model, listOf(AudioWindow(0, 1000))) == null)
        val silent = WhisperEnglish.transcribe(silence, model, emptyList(), null)
        check(silent.segments.isEmpty())
        var cancelled = false
        try { WhisperEnglish.detect(english, model, englishWindows) { throw InterruptedException("test cancellation") } }
        catch (_: InterruptedException) { cancelled = true }
        check(cancelled)
        File(context.filesDir, "english-checkpoint.txt").writeText(
            "English language=en; Russian language=ru; silence empty; cancellation propagated\n" +
            "English text: $text\nload_ms=${result.loadMs}; decode_ms=${result.decodeMs}; audio_ms=${english.durationMs}\n")
    }
}
