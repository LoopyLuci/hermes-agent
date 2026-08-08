package hermes.abi

import java.lang.foreign.*
import java.net.URI
import java.net.URLEncoder
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.nio.charset.StandardCharsets

data class WorkerRegistration(
    val workerId: String,
    val capabilities: CapabilityGrant,
    val status: WorkerStatus
) {
    companion object {
        fun register(workerId: String, supervisorUrl: String): WorkerRegistration {
            val target = URI("$supervisorUrl/v1/workers/$workerId/register")
            val body = "capabilities=default"
            val request = HttpRequest.newBuilder(target)
                .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                .header("Content-Type", "application/x-www-form-urlencoded")
                .build()
            val client = HttpClient.newHttpClient()
            val response = client.send(request, HttpResponse.BodyHandlers.ofString())
            if (response.statusCode() !in 200..299) {
                throw IllegalStateException("Worker registration failed: HTTP ${response.statusCode()}")
            }
            return WorkerRegistration(
                workerId = workerId,
                capabilities = CapabilityGrant.default(),
                status = WorkerStatus.default()
            )
        }
    }
}

object WorkerRegistrationClient {
    fun register(workerId: String, supervisorUrl: String): WorkerRegistration {
        return WorkerRegistration.register(workerId, supervisorUrl)
    }
}
