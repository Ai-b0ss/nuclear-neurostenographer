package ru.neurostenographer.app

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay

/** Short history of the measured microphone RMS. Silence stays flat; no fake speech animation. */
@Composable
internal fun VoiceWaveform(level: Float, color: Color, active: Boolean = true, modifier: Modifier = Modifier) {
    val current by rememberUpdatedState(level)
    var history by remember { mutableStateOf(List(56) { 0f }) }
    LaunchedEffect(active) {
        var envelope = 0f
        if (!active) history = List(56) { 0f }
        while (active) {
            val measured = current.takeIf { it.isFinite() }?.coerceIn(0f,1f) ?: 0f
            // Fast attack and gentle release retain short syllables without jitter.
            envelope += (measured-envelope) * if (measured > envelope) 0.8f else 0.35f
            history = history.drop(1) + envelope
            delay(50)
        }
    }
    Canvas(modifier.fillMaxWidth().height(72.dp).semantics { contentDescription = "Уровень микрофона" }) {
        val center = size.height/2
        val step = size.width/history.size
        drawLine(color.copy(alpha=0.12f),Offset(0f,center),Offset(size.width,center),1.dp.toPx())
        history.forEachIndexed { index, value ->
            val half = (value * (center-5.dp.toPx())).coerceAtLeast(1.dp.toPx())
            val x = step*(index+0.5f)
            drawLine(color.copy(alpha=0.3f+value*0.7f),Offset(x,center-half),Offset(x,center+half),
                strokeWidth=minOf(3.dp.toPx(),step*0.52f),cap=StrokeCap.Round)
        }
    }
}
