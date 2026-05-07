package run.concordance.launcher.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

// ── API request / response models ────────────────────────────────────────────

@Serializable
data class CaptureRequest(
    val text: String,
    val source: String = "android_launcher"
)

@Serializable
data class CaptureResponse(
    val verdict: String,           // "pass" | "quarantine" | "reject"
    val domain: String,
    val gate: String,              // "RED" | "FLOOR" | "BROTHERS" | "GOD"
    val score: Double,
    val packet_hash: String,
    val scripture: String? = null,
    val summary: String? = null,
    val timestamp: String? = null,
    val node_id: String? = null,
    val signature: String? = null
)

@Serializable
data class HealthResponse(
    val status: String,
    val journal_count: Int? = null,
    val node_id: String? = null,
    val version: String? = null
)

@Serializable
data class JournalEntry(
    val text: String? = null,
    val verdict: String,
    val domain: String,
    val gate: String,
    val score: Double,
    val packet_hash: String,
    val scripture: String? = null,
    val timestamp: String? = null
)

// ── Local cache models ────────────────────────────────────────────────────────

data class NodeState(
    val url: String,
    val online: Boolean,
    val latencyMs: Long = -1,
    val nodeId: String? = null,
    val journalCount: Int = 0
)

data class SubmitResult(
    val response: CaptureResponse?,
    val error: String?,
    val fromCache: Boolean = false
) {
    val isSuccess get() = response != null
}

// ── UI state ─────────────────────────────────────────────────────────────────

enum class Gate { RED, FLOOR, BROTHERS, GOD }

enum class GateStatus { IDLE, ACTIVE, PASS, FAIL }

data class GateState(
    val gate: Gate,
    val status: GateStatus = GateStatus.IDLE
)

data class HomeUiState(
    val inputText: String = "",
    val isSubmitting: Boolean = false,
    val result: CaptureResponse? = null,
    val error: String? = null,
    val nodeState: NodeState? = null,
    val recentEntries: List<JournalEntry> = emptyList(),
    val gates: List<GateState> = Gate.entries.map { GateState(it) },
    val showInstallPrompt: Boolean = false,
    val termuxInstalled: Boolean = false   // Termux + Concordance detected on device
) {
    val nodeOnline get() = nodeState?.online == true
}
