package hermes.integration

import hermes.abi.StableAbi
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.nio.file.Path
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

object SupervisorIntegrationTest {
    @JvmStatic
    fun main(args: Array<String>) {
        val supervisorUrl = System.getenv("HERMES_SUPERVISOR_URL")
            ?: throw IllegalStateException("HERMES_SUPERVISOR_URL is required")

        val dll = Path.of(
            System.getenv("HERMES_ABI_DLL")
                ?: "D:/Projects/HermesAgentExpansion/x-runtime/rust/target/release/hermes_runtime_abi.dll"
        )

        val manifest = StableAbi.defaultManifest()
        val fields = StableAbi.manifestFields(manifest)
        if (fields.capabilities.hotReload != 1 || fields.capabilities.capabilityTokens != 1) {
            throw IllegalStateException("supervisor ABI does not advertise hot_reload/capability_tokens")
        }

        val status = httpGet("$supervisorUrl/status")
        val supervisorId = extractJsonString(status, "supervisor_id")
            ?: throw IllegalStateException("missing supervisor_id in status")

        val workerPayload = "{\"id\":\"kotlin-worker\",\"command\":\"python\",\"args\":[\"-c\",\"print('ok')\"],\"capabilities\":[\"task.execute\"],\"autostart\":true}"
        val workerResponse = httpPost("$supervisorUrl/workers", workerPayload)
        val workerId = extractJsonString(workerResponse, "id")
            ?: throw IllegalStateException("missing worker id in spawn response: $workerResponse")

        val start = System.currentTimeMillis()
        httpPost("$supervisorUrl/workers/$workerId/capabilities/renew", "{\"ttl_ms\":60000}")
        val renewLatencyMs = System.currentTimeMillis() - start
        if (renewLatencyMs > 2000) throw IllegalStateException("renew latency too high: $renewLatencyMs ms")

        val metrics = httpGet("$supervisorUrl/metrics")
        val workersTotal = extractJsonLong(metrics, "workers_total")
        if (workersTotal == null) throw IllegalStateException("missing workers_total in metrics")

        println("supervisor_url=$supervisorUrl")
        println("supervisor_id=$supervisorId")
        println("worker_id=$workerId")
        println("abi_hot_reload=${fields.capabilities.hotReload}")
        println("abi_capability_tokens=${fields.capabilities.capabilityTokens}")
        println("renew_latency_ms=$renewLatencyMs")
        println("workers_total=$workersTotal")
        println("supervisor_integration=ok")
    }

    private fun httpGet(url: String): String {
        val conn = URI(url).toURL().openConnection() as HttpURLConnection
        conn.requestMethod = "GET"
        conn.connectTimeout = 2000
        conn.readTimeout = 2000
        return conn.inputStream.bufferedReader().use(BufferedReader::readText)
    }

    private fun httpPost(url: String, body: String): String {
        val conn = URI(url).toURL().openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.doOutput = true
        conn.setRequestProperty("Content-Type", "application/json")
        conn.outputStream.use { it.write(body.toByteArray()) }
        val code = conn.responseCode
        if (code !in 200..299) throw IllegalStateException("POST $url failed: $code")
        return conn.inputStream.bufferedReader().use(BufferedReader::readText)
    }

    private fun extractJsonString(text: String, key: String): String? {
        val pattern = "\"$key\"\\s*:\\s*\"([^\"]+)\"".toRegex()
        return pattern.find(text)?.groupValues?.getOrNull(1)
    }

    private fun extractJsonLong(text: String, key: String): Long? {
        val pattern = "\"$key\"\\s*:\\s*(\\d+)".toRegex()
        return pattern.find(text)?.groupValues?.getOrNull(1)?.toLong()
    }
}
