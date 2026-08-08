package hermes.abi

import java.lang.foreign.*

object HotReloadEdgeCaseTest {
    @JvmStatic
    fun main(args: Array<String>) {
        val manifest = StableAbi.defaultManifest()
        val fields = StableAbi.manifestFields(manifest)

        require(fields.capabilities.hotReload != 0) { "hot reload capability not advertised" }

        // Simulate capability expiry during reload.
        val cap = Arena.ofConfined().allocate(16)
        StableAbi.capabilityDefault(cap)
        StableAbi.capabilityWrite(cap, 1, System.currentTimeMillis())
        StableAbi.capabilityExpire(cap)
        val capFields = StableAbi.capabilityFields(cap)
        require(capFields.expiresAtMs == 0L) { "capability expiry did not clear TTL" }

        // Worker restart mid-renew: default status and manifest must remain stable across calls.
        val status1 = Arena.ofConfined().allocate(24)
        StableAbi.workerStatusDefault(status1)
        StableAbi.workerStatusWrite(status1, 2, 3, 1)
        val status1Fields = StableAbi.workerStatusFields(status1)

        val manifest2 = StableAbi.defaultManifest()
        val manifest2Fields = StableAbi.manifestFields(manifest2)

        require(status1Fields.statusCode == 2)
        require(manifest2Fields.abiVersionMajor == 1L)

        println("hot_reload_edge_cases=ok")
    }
}
