package run.concordance.launcher.vm

import android.app.Application
import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import run.concordance.launcher.api.ConcordanceApi
import run.concordance.launcher.api.NodeDiscovery
import run.concordance.launcher.data.*

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "concordance_prefs")
private val KEY_CUSTOM_URL = stringPreferencesKey("custom_node_url")
private val KEY_REMOTE_URL = stringPreferencesKey("remote_node_url")
private val KEY_CACHED_RECENT = stringPreferencesKey("cached_recent_json")

class HomeViewModel(app: Application) : AndroidViewModel(app) {

    private val prefs = app.dataStore

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    // Active API client — swapped when node changes
    private var api: ConcordanceApi? = null
    private var nodeDiscovery: NodeDiscovery? = null

    init {
        viewModelScope.launch {
            // Load saved node preferences
            prefs.data.first().let { saved ->
                val customUrl = saved[KEY_CUSTOM_URL]
                val remoteUrl = saved[KEY_REMOTE_URL] ?: "https://concordance.run"
                nodeDiscovery = NodeDiscovery(app, customUrl, remoteUrl)
            }
            // Check for Termux + local node
            val discovery = nodeDiscovery!!
            _uiState.update { it.copy(termuxInstalled = discovery.hasLocalTermux) }
            discoverNode()
        }
    }

    fun onInputChanged(text: String) {
        _uiState.update { it.copy(inputText = text, error = null) }
    }

    fun onSubmit() {
        val text = _uiState.value.inputText.trim()
        if (text.isBlank()) return
        val currentApi = api ?: return

        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isSubmitting = true,
                    result = null,
                    error = null,
                    gates = resetGates()
                )
            }

            // Animate through gates while waiting
            val gateJob = launch { animateGates() }

            val result = currentApi.capture(text)

            gateJob.cancel()

            result.fold(
                onSuccess = { response ->
                    _uiState.update {
                        it.copy(
                            isSubmitting = false,
                            result = response,
                            gates = gatesFromVerdict(response),
                            inputText = ""
                        )
                    }
                    // Refresh journal
                    loadJournal(currentApi)
                },
                onFailure = { err ->
                    _uiState.update {
                        it.copy(
                            isSubmitting = false,
                            error = when {
                                err.message?.contains("Unable to resolve host") == true ->
                                    "Node offline — check concordance.local or configure remote"
                                err.message?.contains("timeout") == true ->
                                    "Node took too long to respond"
                                else -> err.message ?: "Unknown error"
                            },
                            gates = resetGates()
                        )
                    }
                }
            )
        }
    }

    fun onClearResult() {
        _uiState.update { it.copy(result = null, error = null, gates = resetGates()) }
    }

    fun retryNodeDiscovery() {
        viewModelScope.launch { discoverNode() }
    }

    fun saveCustomUrl(url: String) {
        viewModelScope.launch {
            prefs.edit { it[KEY_CUSTOM_URL] = url }
            nodeDiscovery = NodeDiscovery(
                getApplication(),
                url.ifBlank { null },
                _uiState.value.nodeState?.url ?: "https://concordance.run"
            )
            discoverNode()
        }
    }

    // ── Private helpers ──────────────────────────────────────────────────────

    private suspend fun discoverNode() {
        val discovery = nodeDiscovery ?: return
        val node = discovery.findNode()
        if (node.online) {
            api = ConcordanceApi(node.url)
            _uiState.update { it.copy(nodeState = node) }
            loadJournal(api!!)
        } else {
            _uiState.update { it.copy(nodeState = node) }
        }
    }

    private suspend fun loadJournal(api: ConcordanceApi) {
        api.journal(limit = 8).onSuccess { entries ->
            _uiState.update { it.copy(recentEntries = entries) }
        }
    }

    private suspend fun animateGates() {
        val gateOrder = listOf(Gate.RED, Gate.FLOOR, Gate.BROTHERS, Gate.GOD)
        for (gate in gateOrder) {
            kotlinx.coroutines.delay(400)
            _uiState.update { state ->
                state.copy(gates = state.gates.map { g ->
                    when {
                        g.gate == gate -> g.copy(status = GateStatus.ACTIVE)
                        else -> g
                    }
                })
            }
        }
    }

    private fun gatesFromVerdict(response: CaptureResponse): List<GateState> {
        val reachedGate = try { Gate.valueOf(response.gate) } catch (_: Exception) { Gate.RED }
        val passed = response.verdict == "pass"
        return Gate.entries.map { g ->
            val ordinal = g.ordinal
            val reachedOrdinal = reachedGate.ordinal
            GateState(
                gate = g,
                status = when {
                    ordinal < reachedOrdinal -> GateStatus.PASS
                    ordinal == reachedOrdinal -> if (passed) GateStatus.PASS else GateStatus.FAIL
                    else -> GateStatus.IDLE
                }
            )
        }
    }

    private fun resetGates() = Gate.entries.map { GateState(it) }
}
