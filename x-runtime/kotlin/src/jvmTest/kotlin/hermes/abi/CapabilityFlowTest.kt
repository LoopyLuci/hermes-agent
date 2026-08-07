package hermes.abi

import java.lang.foreign.*
import java.nio.ByteOrder

object CapabilityFlowTest {
    @JvmStatic
    fun main(args: Array<String>) {
        val manifest = StableAbi.defaultManifest()
        val fields = StableAbi.manifestFields(manifest)
        require(fields.capabilities.capabilityTokens != 0) { "capability tokens not supported" }

        val statusSeg = Arena.ofConfined().allocate(24)
        StableAbi.workerStatusDefault(statusSeg)
        StableAbi.workerStatusWrite(statusSeg, 1, 2, 1)
        val statusFields = StableAbi.workerStatusFields(statusSeg)
        require(statusFields.statusCode == 1)
        require(statusFields.reloadsTotal == 2L)

        val capSeg = Arena.ofConfined().allocate(16)
        StableAbi.capabilityDefault(capSeg)
        StableAbi.capabilityWrite(capSeg, 3, System.currentTimeMillis())
        val capFields = StableAbi.capabilityFields(capSeg)
        require(capFields.granted == 3)
        require(capFields.expiresAtMs > 0)

        println("capability_flow=ok")
    }
}
