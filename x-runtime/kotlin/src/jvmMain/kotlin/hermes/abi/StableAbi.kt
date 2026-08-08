package hermes.abi

import java.lang.foreign.*
import java.nio.ByteOrder
import java.nio.file.Path

object StableAbi {
    data class SymbolCheck(val name: String, val present: Boolean)
    data class ManifestFields(
        val abiVersionMajor: Long,
        val abiVersionMinor: Long,
        val protocolVersionMajor: Long,
        val protocolVersionMinor: Long,
        val capabilities: Capabilities
    ) {
        data class Capabilities(
            val hotReload: Int,
            val durableAtomics: Int,
            val capabilityTokens: Int
        )
    }

    data class WorkerStatusFields(val statusCode: Int, val reloadsTotal: Long, val lastReloadSuccess: Int)
    data class CapabilityFields(val granted: Int, val expiresAtMs: Long)

    private val dll: Path = Path.of(
        "D:/Projects/HermesAgentExpansion/x-runtime/rust/target/release/hermes_runtime_abi.dll"
    )

    private var lookupCache: SymbolLookup? = null

    fun lookup(): SymbolLookup {
        val result = SymbolLookup.libraryLookup(dll, Arena.ofAuto())
        lookupCache = result
        return result
    }

    fun symbols(names: List<String>): List<SymbolCheck> {
        val l = lookup()
        return names.map { SymbolCheck(it, l.find(it).isPresent) }
    }

    fun requireSymbol(name: String): MemorySegment {
        return lookup().find(name).orElse(null) ?: throw IllegalStateException("missing symbol: $name")
    }

    private fun invokeLong(symbol: MemorySegment, name: String): Long {
        val descriptor = FunctionDescriptor.of(ValueLayout.JAVA_LONG)
        val handle = Linker.nativeLinker().downcallHandle(symbol, descriptor)
        return (handle.invoke() as Number).toLong()
    }

    fun defaultManifest(): MemorySegment {
        val size = invokeLong(requireSymbol("stable_abi_manifest_size"), "stable_abi_manifest_size")
        val out = Arena.ofConfined().allocate(size)
        val default = requireSymbol("stable_abi_manifest_default")
        Linker.nativeLinker().downcallHandle(
            default,
            FunctionDescriptor.ofVoid(AddressLayout.ADDRESS)
        ).invokeExact(out)
        return out
    }

    fun manifestFields(manifest: MemorySegment): ManifestFields {
        val bb = manifest.asByteBuffer().order(ByteOrder.LITTLE_ENDIAN)
        return ManifestFields(
            abiVersionMajor = bb.getLong(0),
            abiVersionMinor = bb.getLong(8),
            protocolVersionMajor = bb.getLong(32),
            protocolVersionMinor = bb.getLong(40),
            capabilities = ManifestFields.Capabilities(
                hotReload = bb.getInt(48),
                durableAtomics = bb.getInt(52),
                capabilityTokens = bb.getInt(56)
            )
        )
    }

    fun workerStatusFields(seg: MemorySegment): WorkerStatusFields {
        val bb = seg.asByteBuffer().order(ByteOrder.LITTLE_ENDIAN)
        return WorkerStatusFields(
            statusCode = bb.getInt(0),
            reloadsTotal = bb.getLong(8),
            lastReloadSuccess = bb.getInt(16)
        )
    }

    fun capabilityFields(seg: MemorySegment): CapabilityFields {
        val bb = seg.asByteBuffer().order(ByteOrder.LITTLE_ENDIAN)
        return CapabilityFields(
            granted = bb.getInt(0),
            expiresAtMs = bb.getLong(8)
        )
    }

    fun workerStatusDefault(seg: MemorySegment) {
        Linker.nativeLinker().downcallHandle(
            requireSymbol("stable_abi_worker_status_default"),
            FunctionDescriptor.ofVoid(AddressLayout.ADDRESS)
        ).invokeExact(seg)
    }

    fun workerStatusWrite(seg: MemorySegment, statusCode: Int, reloadsTotal: Long, lastReloadSuccess: Int) {
        val bb = seg.asByteBuffer().order(ByteOrder.LITTLE_ENDIAN)
        bb.putInt(0, statusCode)
        bb.putLong(8, reloadsTotal)
        bb.putInt(16, lastReloadSuccess)
    }

    fun capabilityDefault(seg: MemorySegment) {
        Linker.nativeLinker().downcallHandle(
            requireSymbol("stable_abi_capability_default"),
            FunctionDescriptor.ofVoid(AddressLayout.ADDRESS)
        ).invokeExact(seg)
    }

    fun capabilityWrite(seg: MemorySegment, granted: Int, expiresAtMs: Long) {
        val bb = seg.asByteBuffer().order(ByteOrder.LITTLE_ENDIAN)
        bb.putInt(0, granted)
        bb.putLong(8, expiresAtMs)
    }

    fun capabilityExpire(seg: MemorySegment) {
        val bb = seg.asByteBuffer().order(ByteOrder.LITTLE_ENDIAN)
        bb.putLong(8, 0L)
    }
}

fun stable_abi_worker_status_default(): MemorySegment {
    val out = Arena.ofConfined().allocate(24)
    Linker.nativeLinker().downcallHandle(
        StableAbi.requireSymbol("stable_abi_worker_status_default"),
        FunctionDescriptor.ofVoid(AddressLayout.ADDRESS)
    ).invokeExact(out)
    return out
}

fun stable_abi_capability_default(): MemorySegment {
    val out = Arena.ofConfined().allocate(16)
    Linker.nativeLinker().downcallHandle(
        StableAbi.requireSymbol("stable_abi_capability_default"),
        FunctionDescriptor.ofVoid(AddressLayout.ADDRESS)
    ).invokeExact(out)
    return out
}

fun stable_abi_manifest_default(): MemorySegment = StableAbi.defaultManifest()
