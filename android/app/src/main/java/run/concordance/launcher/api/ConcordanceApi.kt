package run.concordance.launcher.api

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import run.concordance.launcher.data.*
import java.util.concurrent.TimeUnit

private const val TAG = "ConcordanceApi"
private val JSON_TYPE = "application/json; charset=utf-8".toMediaType()

val json = Json {
    ignoreUnknownKeys = true
    isLenient = true
    coerceInputValues = true
}

class ConcordanceApi(private val baseUrl: String) {

    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build()

    suspend fun health(): Result<HealthResponse> = withContext(Dispatchers.IO) {
        runCatching {
            val req = Request.Builder()
                .url("$baseUrl/health")
                .get()
                .build()
            client.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) error("HTTP ${resp.code}")
                json.decodeFromString<HealthResponse>(resp.body!!.string())
            }
        }.onFailure { Log.w(TAG, "health($baseUrl) failed: ${it.message}") }
    }

    suspend fun capture(text: String): Result<CaptureResponse> = withContext(Dispatchers.IO) {
        runCatching {
            val body = json.encodeToString(CaptureRequest(text = text))
                .toRequestBody(JSON_TYPE)
            val req = Request.Builder()
                .url("$baseUrl/capture")
                .post(body)
                .build()
            client.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) error("HTTP ${resp.code}: ${resp.body?.string()}")
                json.decodeFromString<CaptureResponse>(resp.body!!.string())
            }
        }.onFailure { Log.w(TAG, "capture($baseUrl) failed: ${it.message}") }
    }

    suspend fun journal(limit: Int = 8): Result<List<JournalEntry>> = withContext(Dispatchers.IO) {
        runCatching {
            val req = Request.Builder()
                .url("$baseUrl/journal?limit=$limit")
                .get()
                .build()
            client.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) error("HTTP ${resp.code}")
                json.decodeFromString<List<JournalEntry>>(resp.body!!.string())
            }
        }.onFailure { Log.w(TAG, "journal($baseUrl) failed: ${it.message}") }
    }
}
