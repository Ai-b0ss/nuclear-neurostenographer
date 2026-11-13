package ru.neurostenographer.app

import android.graphics.Bitmap
import android.os.Build
import android.os.SystemClock
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Surface
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.BeforeClass
import org.junit.Rule
import org.junit.Test
import ru.neurostenographer.core.*
import java.io.File

/** Real Compose geometry from authored UI states, never an inference/phone test. */
class ProcessingLayoutTest {
    companion object {
        @JvmStatic @BeforeClass fun emulatorOnly() {
            check(BuildConfig.APPLICATION_ID == "ru.neurostenographer.app.layoutqa")
            check(Build.SUPPORTED_ABIS.contains("x86_64") &&
                (Build.HARDWARE.contains("ranchu") || Build.HARDWARE.contains("goldfish")))
        }
    }
    @get:Rule val ui = createComposeRule()

    @Test fun stagesStayStableAndTextRemainsReadableAtLargeFonts() {
        val inst = InstrumentationRegistry.getInstrumentation()
        val runId = requireNotNull(InstrumentationRegistry.getArguments().getString("layoutRunId"))
        val directory = File(inst.targetContext.filesDir, "layout-qa").apply { mkdirs() }
        val rows = JSONArray()
        val result = JSONObject().put("run_id", runId).put("status", "RUNNING")
            .put("execution_environment", "ANDROID_X86_64_EMULATOR_NOT_PHONE")
            .put("scope", "RENDERED_PROCESSING_UI_STATES_NO_INFERENCE").put("rows", rows)
        fun save() = File(directory, "result.json").writeText(result.toString(2))
        var state by mutableStateOf(ScreenState(busy = true))
        var fontScale by mutableFloatStateOf(1f)
        var cancellations = 0
        save()
        ui.setContent {
            val density = LocalDensity.current.density
            CompositionLocalProvider(LocalDensity provides Density(density, fontScale)) {
                StenoTheme {
                    Surface {
                        key(fontScale) {
                        Column(Modifier.width(360.dp).fillMaxHeight()
                            .verticalScroll(rememberScrollState()).padding(16.dp)) {
                            ProcessingCard(state) { cancellations++ }
                        }
                        }
                    }
                }
            }
        }
        try {
            for (scale in listOf(1f, 1.3f, 2f)) {
                val now = SystemClock.elapsedRealtime()
                val base = ScreenState(busy = true, processingStartedAtMs = now,
                    message = "Подготавливаю аудиозапись")
                val states = listOf(
                    base,
                    base.copy(stage = 1),
                    base.copy(stage = 2, message = "Определяю говорящих"),
                    base.copy(stage = 2, message = "Определяю говорящих",
                        diarizationClock = DiarizationTimeEstimate(now, 60_000, 60_000,
                            historyCalibrated = true, completedChunks = 2, totalChunks = 4)),
                    base.copy(stage = 3, message = "Распознаю речь",
                        asrWindowEta = AsrWindowEta.begin(now, 5, 0)),
                    base.copy(stage = 3, message = "Сохраняю расшифровку",
                        asrWindowEta = AsrWindowEta.begin(now, 5, 5)),
                    base.copy(stage = 3, processingClock = AudioProcessingClock(
                        1_240_000, 300_000, 600_000, now, calibrated = true)))
                var expectedTop: Float? = null
                for ((index, value) in states.withIndex()) {
                    ui.runOnIdle { fontScale = scale; state = value }
                    val progress = ui.onNodeWithTag("processing_progress").fetchSemanticsNode().boundsInRoot
                    val textNodes = ui.onAllNodes(SemanticsMatcher.keyIsDefined(
                        SemanticsActions.GetTextLayoutResult), useUnmergedTree = true)
                    val overflow = mutableListOf<String>()
                    repeat(textNodes.fetchSemanticsNodes().size) { n ->
                        val layouts = mutableListOf<TextLayoutResult>()
                        textNodes[n].performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
                        layouts.filter { it.didOverflowHeight || it.didOverflowWidth }
                            .forEach { overflow += it.layoutInput.text.text }
                    }
                    rows.put(JSONObject().put("font_scale", scale).put("state_index", index)
                        .put("stage", value.stage).put("progress_top_px", progress.top)
                        .put("overflow_count", overflow.size))
                    inst.uiAutomation.takeScreenshot()?.let { bitmap ->
                        File(directory, "font-${scale}-state-$index.png").outputStream().use {
                            bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)
                        }
                        bitmap.recycle()
                    }
                    save()
                    assertTrue("Text clipped at fontScale=$scale state=$index: $overflow", overflow.isEmpty())
                    expectedTop?.let { assertEquals("Progress moved at fontScale=$scale state=$index", it, progress.top, 2f) }
                    expectedTop = progress.top
                }
                val before = cancellations
                ui.onNodeWithTag("processing_cancel").performScrollTo().assertIsDisplayed().performClick()
                ui.runOnIdle { assertEquals(before + 1, cancellations); state = state.copy(cancelling = true) }
                ui.onNodeWithTag("processing_cancel").assertIsNotEnabled()
            }
            result.put("status", "PASS")
        } catch (error: Throwable) {
            result.put("status", "FAIL").put("error", error.javaClass.simpleName)
                .put("message", error.message ?: "")
            throw error
        } finally { save() }
    }
}
