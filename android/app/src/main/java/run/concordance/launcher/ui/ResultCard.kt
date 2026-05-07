package run.concordance.launcher.ui

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import run.concordance.launcher.data.CaptureResponse

@Composable
fun ResultCard(
    response: CaptureResponse,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier
) {
    val (verdictColor, verdictLabel) = when (response.verdict) {
        "pass"       -> PassGreen to "PASS"
        "quarantine" -> QuarantineAmber to "QUARANTINE"
        else         -> RejectRed to "REJECT"
    }

    val cardBorder = verdictColor.copy(alpha = 0.4f)

    Card(
        modifier = modifier
            .fillMaxWidth()
            .border(1.dp, cardBorder, RoundedCornerShape(12.dp)),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = BgCard)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            // Header row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // Domain tag
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(4.dp))
                            .background(AccentGold.copy(alpha = 0.15f))
                            .padding(horizontal = 8.dp, vertical = 3.dp)
                    ) {
                        Text(
                            text = response.domain.uppercase(),
                            fontSize = 10.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = AccentGold,
                            letterSpacing = 0.8.sp
                        )
                    }

                    // Verdict chip
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(4.dp))
                            .background(verdictColor.copy(alpha = 0.15f))
                            .padding(horizontal = 8.dp, vertical = 3.dp)
                    ) {
                        Text(
                            text = verdictLabel,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            color = verdictColor,
                            letterSpacing = 0.8.sp
                        )
                    }
                }

                IconButton(
                    onClick = onDismiss,
                    modifier = Modifier.size(24.dp)
                ) {
                    Icon(
                        Icons.Default.Close,
                        contentDescription = "Dismiss",
                        tint = TextMuted,
                        modifier = Modifier.size(16.dp)
                    )
                }
            }

            // Summary
            response.summary?.let { summary ->
                Text(
                    text = summary,
                    fontSize = 14.sp,
                    color = TextPrimary,
                    lineHeight = 20.sp
                )
            }

            // Scripture quote
            response.scripture?.let { scripture ->
                if (scripture.isNotBlank()) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(6.dp))
                            .background(AccentGold.copy(alpha = 0.08f))
                            .padding(12.dp)
                    ) {
                        Text(
                            text = "“$scripture”",
                            fontSize = 13.sp,
                            fontStyle = FontStyle.Italic,
                            color = AccentGold,
                            lineHeight = 19.sp
                        )
                    }
                }
            }

            // Meta row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "Gate: ${response.gate}",
                    fontSize = 11.sp,
                    color = TextMuted
                )
                Text(
                    text = "Score: ${"%.2f".format(response.score)}",
                    fontSize = 11.sp,
                    color = TextMuted
                )
                Text(
                    text = response.packet_hash.take(8) + "…",
                    fontSize = 11.sp,
                    color = TextMuted,
                    fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace
                )
            }
        }
    }
}

@Composable
fun RecentEntryRow(
    verdict: String,
    domain: String,
    text: String?,
    modifier: Modifier = Modifier
) {
    val verdictColor = when (verdict) {
        "pass"       -> PassGreen
        "quarantine" -> QuarantineAmber
        else         -> RejectRed
    }

    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .size(6.dp)
                .clip(androidx.compose.foundation.shape.CircleShape)
                .background(verdictColor)
        )
        Text(
            text = domain.uppercase(),
            fontSize = 10.sp,
            fontWeight = FontWeight.SemiBold,
            color = AccentGold,
            modifier = Modifier.width(80.dp),
            maxLines = 1
        )
        Text(
            text = text ?: "(no text)",
            fontSize = 12.sp,
            color = TextMuted,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f)
        )
    }
}
