package ru.neurostenographer.app

import android.os.Debug
import android.os.SystemClock
import android.util.Log
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Test
import ru.neurostenographer.core.*
import java.io.File

/** Independent test clips through the production C2/A3/FDDT classes. */
class FieldEvaluationDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()

    @Test
    fun compareBaselineAndHybrid(): Unit = runBlocking {
        val args = InstrumentationRegistry.getArguments()
        val filename = requireNotNull(args.getString("evalFile")) { "Pass -e evalFile name.wav" }
        require(Regex("[a-zA-Z0-9_\\-]+\\.wav").matches(filename))
        val mode = args.getString("evalMode") ?: "mixed"
        require(mode == "mixed" || mode == "clean")
        val context = instrumentation.targetContext
        // HONOR may choose the physical SD card as the app's default external location,
        // while adb push writes to /storage/emulated/0. Search only our app-owned dirs.
        val candidateDirs = (
            context.getExternalFilesDirs(null).filterNotNull().map { File(it,"field_eval") } +
            File("/storage/emulated/0/Android/data/" + context.packageName + "/files/field_eval") +
            File("/sdcard/Android/data/" + context.packageName + "/files/field_eval")
        ).distinctBy { it.absolutePath }
        val file = candidateDirs.map { File(it,filename) }.firstOrNull { it.isFile }
            ?: throw IllegalArgumentException("Missing test WAV: " + filename +
                " roots=" + candidateDirs.map { it.absolutePath })
        val output = File(File(context.filesDir,"field_eval_results").apply { mkdirs() },
            filename.removeSuffix(".wav") + ".json")
        output.delete()
        val report = JSONObject()
        report.put("file",filename)
        report.put("mode",mode)
        report.put("source","external independent validation")
        report.put("test_start_uptime",SystemClock.elapsedRealtime())
        report.put("native_heap_start_mib",Debug.getNativeHeapAllocatedSize()/1048576.0)
        try {
            val audio = file.inputStream().buffered().use { PcmWav.read(it) }
            report.put("audio_ms",audio.durationMs)
            require(audio.durationMs in 5000..120000)
            val model = requireNotNull(AsrModelStore(context).current()) { "A3 model missing" }
            AsrModelStore(context).verify(model)
            val started = SystemClock.elapsedRealtime()
            if (mode == "clean") {
                val asr = OfflineAsr.transcribe(audio,model)
                report.put("a3_ms",SystemClock.elapsedRealtime()-started)
                report.put("a3",serialize(TranscriptFusion.mergeReplies(asr.segments)))
            } else {
                val c2 = requireNotNull(NemotronBackend.current(context.filesDir)) { "C2 model missing" }
                val diag=IsolatedDiarization.process(context,audio,c2,backend=NemotronBackend.C2)
                report.put("c2_ms",SystemClock.elapsedRealtime()-started)
                report.put("c2_turns",JSONArray().apply {
                    for (s in diag.turns) put(JSONObject()
                        .put("start_ms",s.startMs).put("end_ms",s.endMs)
                        .put("speaker_id",s.speakerId))
                })
                val baseline = OfflineAsr.transcribe(audio,model,
                    turns=diag.turns,speechWindows=diag.windows,unmerged=true)
                report.put("a3_ms",SystemClock.elapsedRealtime()-started-report.getLong("c2_ms"))
                report.put("baseline",serialize(TranscriptFusion.mergeReplies(baseline.segments)))
                val beforeFddt=SystemClock.elapsedRealtime()
                val hybrid=FddtHybrid.transcribe(context,audio,diag.turns,baseline,
                    checkCancelled={},onProgress={ index,total ->
                        Log.i("FieldEvaluation",filename+" fddt="+index+"/"+total)
                    })
                report.put("fddt_ms",SystemClock.elapsedRealtime()-beforeFddt)
                report.put("hybrid",serialize(hybrid.segments))
                report.put("hybrid_revision",hybrid.modelRevision)
                report.put("changed",hybrid.modelRevision.contains("+fddt_"))
            }
            report.put("native_heap_finish_mib",Debug.getNativeHeapAllocatedSize()/1048576.0)
            report.put("success",true)
            Log.i("FieldEvaluation","PASS "+filename+" mode="+mode+
                " ms="+(SystemClock.elapsedRealtime()-started)+" changed="+report.opt("changed"))
        } catch (t:Throwable) {
            report.put("success",false)
            report.put("error",t.javaClass.name+": "+t.message)
            throw t
        } finally {
            output.writeText(report.toString(2),Charsets.UTF_8)
        }
    }

    private fun serialize(items:List<TranscriptSegment>)=JSONArray().apply {
        for (s in items) put(JSONObject()
            .put("start_ms",s.startMs)
            .put("end_ms",s.endMs)
            .put("speaker_id",s.speakerId)
            .put("text",s.text)
            .put("overlap",s.overlappingSpeech))
    }
}
