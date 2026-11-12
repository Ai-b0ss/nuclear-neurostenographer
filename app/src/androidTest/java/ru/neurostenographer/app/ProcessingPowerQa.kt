package ru.neurostenographer.app

import android.content.Intent
import android.os.PowerManager
import android.os.SystemClock
import androidx.test.platform.app.InstrumentationRegistry

/** Never changes a physical device's display or power settings. */
object ProcessingPowerQa {
    private fun shell(command: String) {
        InstrumentationRegistry.getInstrumentation().uiAutomation
            .executeShellCommand(command).use { descriptor ->
                android.os.ParcelFileDescriptor.AutoCloseInputStream(descriptor).use { it.readBytes() }
            }
    }

    fun foreground() {
        if (!SpeakerBookQaEnvironment.emulator()) return
        val inst = InstrumentationRegistry.getInstrumentation()
        shell("input keyevent 224")
        shell("wm dismiss-keyguard")
        inst.targetContext.startActivity(Intent(inst.targetContext, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP))
        inst.waitForIdleSync()
        SystemClock.sleep(500)
    }

    private fun await(message: String, predicate: () -> Boolean) {
        val end = SystemClock.elapsedRealtime() + 5_000
        while (!predicate() && SystemClock.elapsedRealtime() < end) SystemClock.sleep(50)
        check(predicate()) { message }
    }

    fun screenOffDuringProcessing() {
        if (!SpeakerBookQaEnvironment.emulator()) return
        await("Foreground processing did not acquire its CPU lock") {
            ProcessingService.active.value && ProcessingService.wakeLockHeld
        }
        shell("input keyevent 223")
        val power = InstrumentationRegistry.getInstrumentation().targetContext
            .getSystemService(PowerManager::class.java)
        await("Emulator screen did not turn off") { !power.isInteractive }
    }

    fun stopped() {
        if (!SpeakerBookQaEnvironment.emulator()) return
        await("Processing service/CPU lock leaked after completion or cancellation") {
            !ProcessingService.active.value && !ProcessingService.wakeLockHeld
        }
    }

    fun verifyLifecycle() {
        if (!SpeakerBookQaEnvironment.emulator()) return
        val inst = InstrumentationRegistry.getInstrumentation()
        val context = inst.targetContext
        var cancellations = 0
        var first: AutoCloseable? = null
        var second: AutoCloseable? = null
        try {
            inst.runOnMainSync {
                first = ProcessingService.acquire(context) { cancellations++ }
                second = ProcessingService.acquire(context) { cancellations++ }
            }
            await("Service did not start for two owners") { ProcessingService.active.value && ProcessingService.wakeLockHeld }
            first!!.close()
            first!!.close() // release is idempotent
            SystemClock.sleep(700)
            check(ProcessingService.active.value && ProcessingService.wakeLockHeld)
            second!!.close()
            stopped()
            check(cancellations == 0) { "Normal release cancelled completed work" }
            inst.runOnMainSync { first = ProcessingService.acquire(context) { cancellations++ } }
            await("Service did not restart") { ProcessingService.active.value && ProcessingService.wakeLockHeld }
            inst.runOnMainSync { context.startService(Intent(context, ProcessingService::class.java).setAction(ProcessingService.STOP)) }
            stopped()
            check(cancellations == 1) { "Notification stop must cancel exactly the active owner" }
            // Release before Android delivers onStartCommand must still satisfy its FGS deadline.
            inst.runOnMainSync {
                val early = ProcessingService.acquire(context) { error("Already released owner was cancelled") }
                early.close()
            }
            SystemClock.sleep(1_000)
            stopped()
        } finally {
            first?.close()
            second?.close()
            stopped()
        }
    }
}
