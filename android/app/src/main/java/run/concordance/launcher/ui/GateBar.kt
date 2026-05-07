package run.concordance.launcher.ui

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import run.concordance.launcher.data.Gate
import run.concordance.launcher.data.GateState
import run.concordance.launcher.data.GateStatus

private val gateLabels = mapOf(
    Gate.RED      to "RED",
    Gate.FLOOR    to "FLOOR",
    Gate.BROTHERS to "BROTHERS",
    Gate.GOD      to "GOD"
)

private val gateColors = mapOf(
    Gate.RED      to GateRed,
    Gate.FLOOR    to GateFloor,
    Gate.BROTHERS to GateBrothers,
    Gate.GOD      to GateGod
)

@Composable
fun GateBar(
    gates: List<GateState>,
    modifier: Modifier = Modifier
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.CenterHorizontally),
        verticalAlignment = Alignment.CenterVertically
    ) {
        gates.forEachIndexed { index, gateState ->
            GateChip(gateState = gateState)

            // Connector line between gates
            if (index < gates.size - 1) {
                Box(
                    modifier = Modifier
                        .width(20.dp)
                        .height(1.dp)
                        .background(BorderColor)
                )
            }
        }
    }
}

@Composable
private fun GateChip(gateState: GateState) {
    val baseColor = gateColors[gateState.gate] ?: AccentGold
    val label = gateLabels[gateState.gate] ?: ""

    val targetColor = when (gateState.status) {
        GateStatus.IDLE    -> BorderColor
        GateStatus.ACTIVE  -> baseColor
        GateStatus.PASS    -> baseColor
        GateStatus.FAIL    -> RejectRed
    }

    val animColor by animateColorAsState(
        targetValue = targetColor,
        animationSpec = tween(300),
        label = "gate_color_${gateState.gate}"
    )

    // Pulse animation for ACTIVE state
    val pulseAlpha by rememberInfiniteTransition(label = "pulse_${gateState.gate}").animateFloat(
        initialValue = 0.6f,
        targetValue = 1.0f,
        animationSpec = infiniteRepeatable(
            animation = tween(600, easing = EaseInOutSine),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulse_alpha_${gateState.gate}"
    )

    val alpha = if (gateState.status == GateStatus.ACTIVE) pulseAlpha else 1f

    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.alpha(alpha)
    ) {
        Box(
            modifier = Modifier
                .size(10.dp)
                .clip(CircleShape)
                .background(animColor)
        )
        Spacer(Modifier.height(4.dp))
        Text(
            text = label,
            fontSize = 9.sp,
            fontWeight = FontWeight.Medium,
            color = animColor,
            letterSpacing = 1.sp
        )
    }
}
