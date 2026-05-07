package run.concordance.launcher

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import run.concordance.launcher.ui.*
import run.concordance.launcher.vm.HomeViewModel

class SettingsActivity : ComponentActivity() {

    private val viewModel: HomeViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        setContent {
            ConcordanceTheme {
                SettingsScreen(
                    onBack = { finish() },
                    onSaveCustomUrl = { url ->
                        viewModel.saveCustomUrl(url)
                        finish()
                    }
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SettingsScreen(
    onBack: () -> Unit,
    onSaveCustomUrl: (String) -> Unit
) {
    var customUrl by remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        "Node Settings",
                        color = TextPrimary,
                        fontSize = 16.sp
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Back",
                            tint = TextPrimary
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = BgDeep
                )
            )
        },
        containerColor = BgDeep
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 20.dp, vertical = 16.dp)
                .systemBarsPadding(),
            verticalArrangement = Arrangement.spacedBy(20.dp)
        ) {
            Text(
                text = "The launcher tries these node URLs in order:\n\n" +
                        "1. http://concordance.local:8000 (local Pi/server)\n" +
                        "2. http://localhost:8000 (same device)\n" +
                        "3. Your custom URL (below)\n" +
                        "4. https://concordance.run (remote fallback)",
                fontSize = 13.sp,
                color = TextMuted,
                lineHeight = 20.sp
            )

            OutlinedTextField(
                value = customUrl,
                onValueChange = { customUrl = it },
                label = { Text("Custom node URL", color = TextMuted) },
                placeholder = { Text("http://192.168.1.100:8000", color = TextMuted) },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                colors = OutlinedTextFieldDefaults.colors(
                    focusedContainerColor = BgInput,
                    unfocusedContainerColor = BgInput,
                    focusedBorderColor = AccentGold.copy(alpha = 0.6f),
                    unfocusedBorderColor = BorderColor,
                    focusedTextColor = TextPrimary,
                    unfocusedTextColor = TextPrimary,
                    focusedLabelColor = AccentGold,
                    cursorColor = AccentGold
                ),
                shape = RoundedCornerShape(10.dp)
            )

            Button(
                onClick = { onSaveCustomUrl(customUrl.trim()) },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp),
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = AccentGold,
                    contentColor = BgDeep
                )
            ) {
                Text("Save & Reconnect", fontSize = 15.sp)
            }

            Divider(color = BorderColor)

            Text(
                text = "ABOUT THIS DEVICE",
                fontSize = 10.sp,
                color = TextMuted,
                letterSpacing = 1.sp
            )
            Text(
                text = "Concordance Launcher v1.0\n" +
                        "Connects to any Concordance node on your network or remotely.\n" +
                        "No data leaves your device except what you submit to the engine.",
                fontSize = 13.sp,
                color = TextMuted,
                lineHeight = 20.sp
            )
        }
    }
}
