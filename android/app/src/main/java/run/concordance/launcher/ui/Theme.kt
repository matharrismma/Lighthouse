package run.concordance.launcher.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// ── Color palette (mirrors site/index.html CSS variables) ────────────────────
val BgDeep       = Color(0xFF0F0D11)   // --bg
val BgCard       = Color(0xFF1A1720)   // --bg-card
val BgInput      = Color(0xFF211E28)   // --bg-input
val AccentGold   = Color(0xFFC9A87C)   // --accent (warm gold)
val AccentMuted  = Color(0xFF8A7255)   // --accent-muted
val TextPrimary  = Color(0xFFE8E0D0)   // --text
val TextMuted    = Color(0xFF9A9090)   // --text-muted
val PassGreen    = Color(0xFF6FC47C)   // --pass
val QuarantineAmber = Color(0xFFE8A030) // --quarantine
val RejectRed    = Color(0xFFE05050)   // --reject
val BorderColor  = Color(0xFF2E2830)   // --border

// Gate colors
val GateRed      = Color(0xFFE05050)
val GateFloor    = Color(0xFFE8A030)
val GateBrothers = Color(0xFF6FC47C)
val GateGod      = Color(0xFFC9A87C)

private val ConcordanceColorScheme = darkColorScheme(
    primary       = AccentGold,
    onPrimary     = BgDeep,
    secondary     = AccentMuted,
    background    = BgDeep,
    surface       = BgCard,
    onSurface     = TextPrimary,
    onBackground  = TextPrimary,
    outline       = BorderColor,
    error         = RejectRed
)

@Composable
fun ConcordanceTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = ConcordanceColorScheme,
        content = content
    )
}
