package ru.neurostenographer.app

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.widget.TextView
import ru.neurostenographer.core.*
import java.io.File

/** Opt-in private emulator harness. No synthetic ASR text, network or private audio. */
class AsrSmokeActivity : Activity() {
    private var worker: Thread? = null
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val view = TextView(this).apply { textSize = 16f; setPadding(24, 24, 24, 24) }
        setContentView(view)
        fun report(text: String) {
            Log.i("AsrEvidence", text)
            runOnUiThread { view.text = text }
        }
        report("RUNNING real Android ASR. Installing checksum-verified public model…")
        worker = Thread {
            val checkCancelled = { check(!Thread.currentThread().isInterrupted) { "Harness interrupted" } }
            try {
                check(checkSelfPermission(Manifest.permission.INTERNET) == PackageManager.PERMISSION_DENIED)
                val store = AsrModelStore(this)
                val model = assets.open("gigaam-v3.zip").use { store.install(it, checkCancelled) }
                val audio = assets.open("example.wav").use { PcmWav.read(it) }
                var first: List<TranscriptSegment>? = null
                val timings = mutableListOf<String>()
                repeat(2) { index ->
                    report("RUNNING actual Android JNI inference ${index + 1}/2. ABI ${Build.SUPPORTED_ABIS.joinToString()}")
                    store.verify(model, checkCancelled)
                    val result = OfflineAsr.transcribe(audio, model, checkCancelled)
                    check(result.segments.all { it.speakerId == null && !it.attributionReliable && it.endMs <= audio.durationMs })
                    val text = result.segments.joinToString(" ") { it.text }
                    check(text.contains("у лукоморья дуб зеленый")) { "Fixture phrase missing: $text" }
                    first?.let { check(it == result.segments) { "Repeated output differs" } }
                    first = result.segments
                    timings += "run=${index + 1} audio_ms=${result.audioMs} load_ms=${result.loadMs} decode_ms=${result.decodeMs}"
                    Log.i("AsrEvidence", timings.last() + " text=" + text)
                }
                report("RUNNING silence and short-tail negative tests…")
                check(OfflineAsr.transcribe(PcmAudio(FloatArray(32000), 16000), model, checkCancelled).segments.isEmpty())
                check(OfflineAsr.transcribe(PcmAudio(FloatArray(20 * 16000 + 160), 16000), model, checkCancelled).segments.isEmpty())
                val segments = requireNotNull(first)
                val json = TranscriptExport.json(segments, TranscriptProvenance(
                    "sherpa-onnx-1.12.20/gigaam-v3-ctc-int8", AsrModelStore.REVISION, "input_windows", "not_run"))
                File(filesDir, "android-asr-evidence.json").writeText(json)
                val text = "PASS REAL ANDROID ASR\nSDK ${Build.VERSION.SDK_INT}; ABI ${Build.SUPPORTED_ABIS.joinToString()}\n" +
                    "INTERNET permission DENIED\nModel SHA-256 verified\nRepeated output, silence, short tail PASS\n" +
                    timings.joinToString("\n") + "\nSpeaker inference NOT_RUN\n\n" + segments.joinToString("\n") { it.text }
                report(text)
            } catch (e: Throwable) {
                Log.e("AsrEvidence", "FAIL actual Android ASR", e)
                report("FAIL REAL ANDROID ASR: ${e.javaClass.simpleName}: ${e.message}")
            }
        }.apply { name = "AsrSmokeHarness"; start() }
    }
    override fun onDestroy() { worker?.interrupt(); super.onDestroy() }
}
