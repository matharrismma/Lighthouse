package run.concordance.launcher.ui

import androidx.compose.animation.*
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import run.concordance.launcher.data.HomeUiState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    uiState: HomeUiState,
    onInputChanged: (String) -> Unit,
    onSubmit: () -> Unit,
    onClearResult: () -> Unit,
    onRetryNode: () -> Unit,
    onSettingsClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val focusRequester = remember { FocusRequester() }

    LazyColumn(
        modifier = modifier
            .fillMaxSize()
            .background(BgDeep)
            .systemBarsPadding(),
        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // ── Nav bar ──────────────────────────────────────────────────────
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "CONCORDANCE",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = AccentGold,
                    letterSpacing = 2.sp
                )

                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // Node status dot
                    val nodeOnline = uiState.nodeState?.online == true
                    Box(
                        modifier = Modifier
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(if (nodeOnline) PassGreen else RejectRed)
                            .clickable { onRetryNode() }
                    )
                    Text(
                        text = if (nodeOnline) "ONLINE" else "OFFLINE",
                        fontSize = 9.sp,
                        color = if (nodeOnline) PassGreen else RejectRed,
                        letterSpacing = 1.sp
                    )

                    IconButton(
                        onClick = onSettingsClick,
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(
                            Icons.Default.Settings,
                            contentDescription = "Settings",
                            tint = TextMuted,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }
        }

        // ── Hero ─────────────────────────────────────────────────────────
        item {
            Spacer(Modifier.height(24.dp))
            Text(
                text = "What are you carrying?",
                fontSize = 26.sp,
                fontWeight = FontWeight.Light,
                color = TextPrimary,
                textAlign = TextAlign.Center,
                lineHeight = 34.sp,
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(Modifier.height(6.dp))
            Text(
                text = "Bring what's heavy. The engine weighs it.",
                fontSize = 14.sp,
                color = TextMuted,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth()
            )
        }

        // ── Gate bar ─────────────────────────────────────────────────────
        item {
            GateBar(gates = uiState.gates)
        }

        // ── Input ────────────────────────────────────────────────────────
        item {
            OutlinedTextField(
                value = uiState.inputText,
                onValueChange = onInputChanged,
                modifier = Modifier
                    .fillMaxWidth()
                    .defaultMinSize(minHeight = 100.dp)
                    .focusRequester(focusRequester),
                placeholder = {
                    Text(
                        text = "A decision, a claim, a scripture you're wrestling with…",
                        color = TextMuted,
                        fontSize = 14.sp,
                        lineHeight = 20.sp
                    )
                },
                keyboardOptions = KeyboardOptions(
                    capitalization = KeyboardCapitalization.Sentences,
                    imeAction = ImeAction.Send
                ),
                keyboardActions = KeyboardActions(
                    onSend = { onSubmit() }
                ),
                maxLines = 8,
                colors = OutlinedTextFieldDefaults.colors(
                    focusedContainerColor = BgInput,
                    unfocusedContainerColor = BgInput,
                    focusedBorderColor = AccentGold.copy(alpha = 0.6f),
                    unfocusedBorderColor = BorderColor,
                    focusedTextColor = TextPrimary,
                    unfocusedTextColor = TextPrimary,
                    cursorColor = AccentGold
                ),
                shape = RoundedCornerShape(10.dp),
                textStyle = LocalTextStyle.current.copy(
                    fontSize = 15.sp,
                    lineHeight = 22.sp
                ),
                enabled = !uiState.isSubmitting
            )
        }

        // ── Submit button ─────────────────────────────────────────────────
        item {
            Button(
                onClick = onSubmit,
                enabled = uiState.inputText.isNotBlank() && !uiState.isSubmitting,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp),
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = AccentGold,
                    contentColor = BgDeep,
                    disabledContainerColor = AccentGold.copy(alpha = 0.3f),
                    disabledContentColor = BgDeep.copy(alpha = 0.5f)
                )
            ) {
                if (uiState.isSubmitting) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        color = BgDeep,
                        strokeWidth = 2.dp
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = "Running gates…",
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 15.sp
                    )
                } else {
                    Icon(
                        Icons.Default.Send,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = "Submit to the Engine",
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 15.sp
                    )
                }
            }
        }

        // ── Error / offline prompt ────────────────────────────────────────
        uiState.error?.let { error ->
            item {
                Card(
                    colors = CardDefaults.cardColors(containerColor = RejectRed.copy(alpha = 0.1f)),
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, RejectRed.copy(alpha = 0.3f), RoundedCornerShape(8.dp))
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text(text = error, color = RejectRed, fontSize = 13.sp)

                        // If Termux is installed but node isn't running, show how to start it
                        if (uiState.termuxInstalled && !uiState.nodeOnline) {
                            Spacer(Modifier.height(8.dp))
                            Text(
                                text = "Termux detected on this device. Open Termux to start your local node — it launches automatically.",
                                color = AccentGold,
                                fontSize = 12.sp,
                                lineHeight = 17.sp
                            )
                            Spacer(Modifier.height(6.dp))
                            OutlinedButton(
                                onClick = { /* handled by MainActivity */ },
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(6.dp),
                                border = androidx.compose.foundation.BorderStroke(1.dp, AccentGold.copy(alpha = 0.5f))
                            ) {
                                Text("Open Termux", color = AccentGold, fontSize = 13.sp)
                            }
                        }
                    }
                }
            }
        }

        // ── Result card ───────────────────────────────────────────────────
        uiState.result?.let { result ->
            item {
                AnimatedVisibility(
                    visible = true,
                    enter = fadeIn() + slideInVertically { it / 2 }
                ) {
                    ResultCard(
                        response = result,
                        onDismiss = onClearResult
                    )
                }
            }
        }

        // ── Recent verdicts ───────────────────────────────────────────────
        if (uiState.recentEntries.isNotEmpty()) {
            item {
                Spacer(Modifier.height(8.dp))
                HorizontalDivider(color = BorderColor)
                Spacer(Modifier.height(8.dp))
                Text(
                    text = "RECENT",
                    fontSize = 10.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = TextMuted,
                    letterSpacing = 1.5.sp
                )
            }
            items(uiState.recentEntries) { entry ->
                RecentEntryRow(
                    verdict = entry.verdict,
                    domain = entry.domain,
                    text = entry.text
                )
            }
        }

        // ── Node info footer ──────────────────────────────────────────────
        uiState.nodeState?.let { node ->
            item {
                Spacer(Modifier.height(16.dp))
                Text(
                    text = buildString {
                        if (node.online) {
                            append(node.url)
                            node.nodeId?.let { append(" · ${it.take(12)}…") }
                            append(" · ${node.journalCount} entries")
                        } else {
                            append("No node found — check your network or configure a remote node")
                        }
                    },
                    fontSize = 10.sp,
                    color = TextMuted.copy(alpha = 0.6f),
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth()
                )
            }
        }

        item { Spacer(Modifier.height(40.dp)) }
    }
}
