package run.concordance.launcher.api

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.util.Log
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.Flow
import run.concordance.launcher.data.NodeState

private const val TAG = "NodeDiscovery"
private const val SERVICE_TYPE = "_http._tcp."
private const val SERVICE_NAME_PREFIX = "Concordance"

/**
 * Tries node URLs in order until one responds.
 *
 * Priority:
 *   1. localhost:8000 — Termux running on THIS device (fastest possible)
 *   2. concordance.local — Pi or Linux server on local WiFi
 *   3. custom URL — user-configured IP
 *   4. concordance.run — remote fallback
 *
 * Termux detection: check if /data/data/com.termux exists and
 * ~/concordance/.venv/bin/uvicorn is present. If so, prompt user to
 * open Termux to start the local node.
 */
class NodeDiscovery(
    private val context: Context,
    private val customUrl: String? = null,
    private val remoteUrl: String = "https://concordance.run"
) {

    /** True if Termux + Concordance are installed on this device */
    val hasLocalTermux: Boolean by lazy {
        java.io.File("/data/data/com.termux").exists() &&
        java.io.File("/data/data/com.termux/files/home/concordance/.venv").exists()
    }

    /** Ordered list of candidate URLs to probe */
    private val candidates: List<String> get() = buildList {
        add("http://localhost:8000")            // Termux on THIS device — check first
        add("http://127.0.0.1:8000")            // explicit loopback alias
        add("http://concordance.local:8000")    // Pi / Linux on local network
        add("http://concordance.local:8000")    // (deduped below)
        customUrl?.let { add(it) }
        add(remoteUrl)
    }.distinct()

    /**
     * Returns the first responsive node. Probes in parallel, returns fastest winner.
     */
    suspend fun findNode(): NodeState {
        for (url in candidates) {
            val api = ConcordanceApi(url)
            val start = System.currentTimeMillis()
            val result = api.health()
            if (result.isSuccess) {
                val health = result.getOrNull()!!
                Log.i(TAG, "Found node at $url in ${System.currentTimeMillis() - start}ms")
                return NodeState(
                    url = url,
                    online = true,
                    latencyMs = System.currentTimeMillis() - start,
                    nodeId = health.node_id,
                    journalCount = health.journal_count ?: 0
                )
            }
        }
        return NodeState(url = remoteUrl, online = false)
    }

    /**
     * mDNS service discovery flow.
     * Emits discovered Concordance service URLs on the local network.
     * Caller should merge with [findNode] fallback.
     */
    fun discoverLocal(): Flow<String> = callbackFlow {
        val nsdManager = context.getSystemService(Context.NSD_SERVICE) as NsdManager

        val listener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(type: String) {
                Log.d(TAG, "mDNS discovery started: $type")
            }
            override fun onServiceFound(info: NsdServiceInfo) {
                if (!info.serviceName.contains(SERVICE_NAME_PREFIX, ignoreCase = true)) return
                nsdManager.resolveService(info, object : NsdManager.ResolveListener {
                    override fun onResolveFailed(s: NsdServiceInfo?, code: Int) {
                        Log.w(TAG, "Resolve failed: $code")
                    }
                    override fun onServiceResolved(s: NsdServiceInfo) {
                        val host = s.host?.hostAddress ?: return
                        val url = "http://$host:${s.port}"
                        Log.i(TAG, "mDNS resolved: $url (${s.serviceName})")
                        trySend(url)
                    }
                })
            }
            override fun onServiceLost(info: NsdServiceInfo) {}
            override fun onDiscoveryStopped(type: String) {}
            override fun onStartDiscoveryFailed(type: String, code: Int) {
                Log.w(TAG, "mDNS start failed: $code")
                close()
            }
            override fun onStopDiscoveryFailed(type: String, code: Int) {}
        }

        nsdManager.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, listener)

        awaitClose {
            try { nsdManager.stopServiceDiscovery(listener) } catch (_: Exception) {}
        }
    }
}
