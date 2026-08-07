package hermes.abi

import java.lang.foreign.*

object WorkerLifecycle {
    fun defaultStatus(): WorkerStatus = WorkerStatus.default()
    fun reloadCount(status: WorkerStatus): Long = status.reloadsTotal
    fun isHealthy(status: WorkerStatus): Boolean = status.statusCode == 0L && status.reloadsTotal == 0L
}

data class WorkerStatus(
    val statusCode: Long,
    val reloadsTotal: Long
) {
    companion object {
        fun default(): WorkerStatus {
            val bytes = stable_abi_worker_status_default()
            return WorkerStatus(
                statusCode = bytes.getAtIndex(ValueLayout.JAVA_INT, 0).toLong(),
                reloadsTotal = bytes.getAtIndex(ValueLayout.JAVA_LONG, 1)
            )
        }
    }
}
