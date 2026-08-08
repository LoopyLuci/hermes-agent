package hermes.abi

class WorkerLifecycleTest {
    companion object {
        @JvmStatic
        fun main(args: Array<String>) {
            val status = WorkerLifecycle.defaultStatus()
            if (WorkerLifecycle.isHealthy(status)) {
                println("worker_default_status_healthy=ok")
            } else {
                throw IllegalStateException("default worker status is not healthy")
            }
        }
    }
}
