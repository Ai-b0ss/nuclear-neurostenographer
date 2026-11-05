package ru.neurostenographer.app

import android.app.ActivityManager
import android.os.Debug
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import ru.neurostenographer.core.PcmWav
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import kotlin.concurrent.thread

/** Opt-in AMI manual-reference diarization probe on the Android emulator. */
class AmiDiarizationProbeTest {
    @Test fun fourSpeakerMeeting(): Unit = runBlocking {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val assets = instrumentation.context.assets
        val case = InstrumentationRegistry.getArguments().getString("case") ?: "development"
        require(case in setOf("development", "holdout"))
        val name = if (case == "development") "ES2004a-360-600" else "IS1009a-360-600"
        val expected = JSONObject(assets.open("ami-meeting/$name.reference.json").bufferedReader().use { it.readText() })
        val digest = MessageDigest.getInstance("SHA-256")
        assets.open("ami-meeting/$name.wav").use { input ->
            val buffer = ByteArray(1024 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        val hash = digest.digest().joinToString("") { "%02x".format(it) }
        assertEquals(expected.getString("audio_sha256"), hash)
        val audio = assets.open("ami-meeting/$name.wav").use { PcmWav.read(it) }
        assertEquals(expected.getLong("audio_duration_ms"), audio.durationMs)
        val c2 = assets.open("nemotron.zip").use { NemotronDiarization.install(context.filesDir, it) }
        val manager = context.getSystemService(ActivityManager::class.java)
        val worker = AtomicInteger(0)
        val active = AtomicBoolean(true)
        val peak = IntArray(3)
        val sampler = thread {
            while (active.get()) {
                val app = Debug.MemoryInfo().also(Debug::getMemoryInfo).totalPss
                val pid = worker.get()
                val remote = if (pid == 0) 0 else
                    manager.getProcessMemoryInfo(intArrayOf(pid)).firstOrNull()?.totalPss ?: 0
                peak[0] = maxOf(peak[0], app)
                peak[1] = maxOf(peak[1], remote)
                peak[2] = maxOf(peak[2], app + remote)
                Thread.sleep(250)
            }
        }
        val start = System.nanoTime()
        val output = try {
            IsolatedDiarization.process(context, audio, c2, backend = NemotronBackend.C2,
                onWorkerStarted = worker::set)
        } finally {
            active.set(false)
            sampler.join()
        }
        val turns = JSONArray()
        for (turn in output.turns) {
            turns.put(JSONObject().put("start_ms", turn.startMs).put("end_ms", turn.endMs)
                .put("speaker_id", turn.speakerId))
        }
        val result = JSONObject().put("audio_sha256", hash)
            .put("audio_duration_ms", audio.durationMs).put("diarization", turns)
            .put("backend", NemotronBackend.C2).put("wall_ms", (System.nanoTime() - start) / 1_000_000)
            .put("load_ms", output.loadMs).put("infer_ms", output.processMs)
            .put("peak_app_pss_kib", peak[0]).put("peak_worker_pss_kib", peak[1])
            .put("peak_total_pss_kib", peak[2])
        File(context.filesDir, "ami-c2-$case-evidence.json").writeText(result.toString())
    }
}
