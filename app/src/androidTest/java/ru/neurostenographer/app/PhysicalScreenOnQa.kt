package ru.neurostenographer.app

import android.app.KeyguardManager
import android.content.Intent
import android.os.PowerManager
import android.os.SystemClock
import android.view.WindowManager
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.runner.lifecycle.ActivityLifecycleMonitorRegistry
import androidx.test.runner.lifecycle.Stage

/** Owns only a flag on our isolated QA Activity. No power keys or global settings. */
object PhysicalScreenOnQa {
    fun begin(): AutoCloseable {
        val inst = InstrumentationRegistry.getInstrumentation()
        val target = inst.targetContext
        check(target.packageName == "ru.neurostenographer.app.solhigh")
        check(target.getSystemService(PowerManager::class.java).isInteractive &&
            !target.getSystemService(KeyguardManager::class.java).isKeyguardLocked) {
            "Unlock HONOR for foreground screen-on QA"
        }
        target.startActivity(Intent(target, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP))
        inst.waitForIdleSync()
        var activity: MainActivity? = null
        var previouslyKeptOn = false
        val deadline = SystemClock.elapsedRealtime() + 10_000
        while (activity == null && SystemClock.elapsedRealtime() < deadline) {
            inst.runOnMainSync {
                val resumed = ActivityLifecycleMonitorRegistry.getInstance()
                    .getActivitiesInStage(Stage.RESUMED).filterIsInstance<MainActivity>().firstOrNull()
                if (resumed != null) {
                    previouslyKeptOn = resumed.window.attributes.flags and
                        WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON != 0
                    resumed.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                    activity = resumed
                }
            }
            if (activity == null) SystemClock.sleep(50)
        }
        val owned = checkNotNull(activity) { "QA Activity did not resume" }
        return AutoCloseable {
            inst.runOnMainSync {
                if (!previouslyKeptOn && !owned.isDestroyed)
                    owned.window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            }
        }
    }
}
