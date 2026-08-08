package hermes.abi

import java.lang.foreign.*
import java.nio.file.*

object StableAbiCoroutineTest {
    @JvmStatic
    fun main(args: Array<String>) {
        val manifest = StableAbi.defaultManifest()
        println("manifest_default=ok")

        val fields = StableAbi.manifestFields(manifest)
        println("abi_major=${fields.abiVersionMajor}")
        println("abi_minor=${fields.abiVersionMinor}")
        println("protocol_major=${fields.protocolVersionMajor}")
        println("protocol_minor=${fields.protocolVersionMinor}")
        println("hot_reload=${fields.capabilities.hotReload}")
        println("durable_atomics=${fields.capabilities.durableAtomics}")
        println("capability_tokens=${fields.capabilities.capabilityTokens}")
        if (fields.abiVersionMajor <= 0) throw IllegalStateException("abi_version_major must be > 0")
        if (fields.protocolVersionMajor <= 0) throw IllegalStateException("protocol_version_major must be > 0")
        if (fields.capabilities.hotReload != 1 || fields.capabilities.durableAtomics != 1 || fields.capabilities.capabilityTokens != 1) {
            throw IllegalStateException("capabilities not populated")
        }

        val ws = Arena.ofConfined().allocate(24)
        val wsSymbol = StableAbi.requireSymbol("stable_abi_worker_status_default")
        Linker.nativeLinker().downcallHandle(
            wsSymbol,
            FunctionDescriptor.ofVoid(AddressLayout.ADDRESS)
        ).invokeExact(ws)
        val wsFields = StableAbi.workerStatusFields(ws)
        println("worker_status_code=${wsFields.statusCode}")
        println("worker_reloads_total=${wsFields.reloadsTotal}")
        if (wsFields.statusCode != 0 || wsFields.reloadsTotal != 0L) throw IllegalStateException("worker status default not zeroed")

        val cap = Arena.ofConfined().allocate(16)
        val capSymbol = StableAbi.requireSymbol("stable_abi_capability_default")
        Linker.nativeLinker().downcallHandle(
            capSymbol,
            FunctionDescriptor.ofVoid(AddressLayout.ADDRESS)
        ).invokeExact(cap)
        val capFields = StableAbi.capabilityFields(cap)
        println("capability_granted=${capFields.granted}")
        if (capFields.granted != 0) throw IllegalStateException("capability default not zeroed")
    }
}
