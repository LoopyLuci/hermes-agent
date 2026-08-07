package hermes.abi

object StableAbiBenchmark {
    fun run() {
        val names = listOf(
            "stable_abi_manifest_size",
            "stable_abi_manifest_default",
            "stable_abi_manifest_round_trip",
            "stable_abi_worker_status_default",
            "stable_abi_capability_default"
        )
        val iterations = 1000
        val start = System.nanoTime()
        repeat(iterations) {
            val checks = StableAbi.symbols(names)
            if (checks.any { !it.present }) throw IllegalStateException("missing symbol in benchmark")
        }
        val durationNanos = System.nanoTime() - start
        val durationMs = durationNanos / 1_000_000.0
        val perCallMs = durationMs / iterations
        println("benchmark_symbol_lookup iterations=$iterations duration_ms=$durationMs per_call_ms=$perCallMs")
    }
}
