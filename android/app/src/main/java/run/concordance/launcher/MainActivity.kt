package run.concordance.launcher

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import run.concordance.launcher.ui.ConcordanceTheme
import run.concordance.launcher.ui.HomeScreen
import run.concordance.launcher.vm.HomeViewModel

class MainActivity : ComponentActivity() {

    private val viewModel: HomeViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        setContent {
            ConcordanceTheme {
                val uiState by viewModel.uiState.collectAsState()

                HomeScreen(
                    uiState = uiState,
                    onInputChanged = viewModel::onInputChanged,
                    onSubmit = viewModel::onSubmit,
                    onClearResult = viewModel::onClearResult,
                    onRetryNode = viewModel::retryNodeDiscovery,
                    onSettingsClick = {
                        startActivity(Intent(this, SettingsActivity::class.java))
                    }
                )
            }
        }
    }

    /** Back press on the launcher = do nothing (we ARE the home screen) */
    override fun onBackPressed() {
        // Intentionally swallow — home screens don't back-navigate
    }
}
