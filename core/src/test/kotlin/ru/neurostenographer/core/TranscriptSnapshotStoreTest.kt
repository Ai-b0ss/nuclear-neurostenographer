package ru.neurostenographer.core

import java.io.File
import java.nio.file.Files

fun testTranscriptSnapshotStore() {
    val root = Files.createTempDirectory("realtime-snapshot-test").toFile()
    try {
        val basic = File(root, "basic").apply { mkdirs() }
        val store = TranscriptSnapshotStore(basic)
        check(store.current() == null)
        val first = store.publish("""{"text":"привет"}""", "привет\n", "1\n00:00:00,000 --> 00:00:01,000\nпривет\n", 1000, false)
        check(first.number == 1L && first.state == "PROVISIONAL")
        check(store.current()?.json?.readText() == """{"text":"привет"}""")
        check(File(basic, "transcript.json").readText() == first.json.readText())
        check(File(basic, "transcript-current.json").readText().contains("PROVISIONAL"))
        val second = store.publish("""{"text":"привет!","speaker":"Speaker 1"}""",
            "Speaker 1: привет!\n", "1\n00:00:00,000 --> 00:00:01,000\nпривет!\n", 1000, true)
        check(second.number == 2L && second.state == "FINAL" && second.audioMs == 1000L)
        check(store.current()?.srt?.readText() == second.srt.readText())
        check(File(basic, "transcript-current.json").readText().contains("FINAL"))
        check(TranscriptSnapshotStore(basic).current()?.number == 2L)
        repeat(50) { i ->
            store.publish("{\"step\":$i}", "шаг $i\n", "шаг $i\n", i.toLong(), false)
        }
        check(store.current()?.number == 52L)
        check(File(basic, "transcript-versions").listFiles()!!.count { it.name.startsWith("v") } == 3)
        check(runCatching { store.publish("x", "x", "x", 3_600_001L, false) }.isFailure)

        val stages = listOf("after-json", "after-txt", "after-srt", "after-snapshot",
            "after-directory", "after-pointer", "after-compat-json", "after-compat-txt")
        stages.forEach { stage ->
            val folder = File(root, stage).apply { mkdirs() }
            TranscriptSnapshotStore(folder).publish("OLD", "OLD", "OLD", 100, false)
            val failing = TranscriptSnapshotStore(folder) { at ->
                if (at == stage) error("Injected crash at $stage")
            }
            check(runCatching { failing.publish("NEW", "NEW", "NEW", 200, true) }.isFailure)
            val recovered = TranscriptSnapshotStore(folder)
            val current = requireNotNull(recovered.current())
            val pointedNew = stage == "after-pointer" || stage.startsWith("after-compat-")
            check(current.number == if (pointedNew) 2L else 1L) {
                "Atomic pointer violated at $stage"
            }
            check(current.json.readText() == if (pointedNew) "NEW" else "OLD")
            check(current.txt.readText() == if (pointedNew) "NEW" else "OLD")
            check(current.srt.readText() == if (pointedNew) "NEW" else "OLD")
            // A restart must not collide with an incomplete staging directory.
            val next = recovered.publish("RECOVERED", "RECOVERED", "RECOVERED", 300, true)
            check(next.number >= 3L && recovered.current()?.number == next.number)
            check(recovered.current()?.txt?.readText() == "RECOVERED")
        }

        val altered = File(root, "altered").apply { mkdirs() }
        val valid = TranscriptSnapshotStore(altered).publish("genuine", "genuine", "genuine", 100, true)
        valid.srt.appendText("tampered")
        check(runCatching { TranscriptSnapshotStore(altered) }.isFailure) {
            "Corrupted revision must be rejected, not silently accepted"
        }
        val brokenPointer = File(root, "pointer-corrupt").apply { mkdirs() }
        TranscriptSnapshotStore(brokenPointer).publish("valid", "valid", "valid", 0, false)
        File(brokenPointer, "transcript-current.json").writeText("partial")
        check(runCatching { TranscriptSnapshotStore(brokenPointer) }.isFailure)
        println("PASS atomic transcript snapshots: 3 formats, restart, 8 crash cut-points, corruption, retention")
    } finally {
        root.deleteRecursively()
    }
}
