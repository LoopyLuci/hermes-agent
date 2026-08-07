package hermes.abi

import java.lang.foreign.MemorySegment
import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Semaphore

object StableAbiCoroutine {
    private val concurrencyLimit = Semaphore(8)

    suspend fun <T> withFfiLimit(block: suspend () -> T): T = withContext(Dispatchers.IO) {
        concurrencyLimit.acquire()
        try {
            block()
        } finally {
            concurrencyLimit.release()
        }
    }

    suspend fun symbolsAsync(names: List<String>): List<StableAbi.SymbolCheck> =
        withFfiLimit { StableAbi.symbols(names) }

    suspend fun defaultManifestAsync(): MemorySegment =
        withFfiLimit { StableAbi.defaultManifest() }

    suspend fun manifestFieldsAsync(manifest: MemorySegment): StableAbi.ManifestFields =
        withFfiLimit { StableAbi.manifestFields(manifest) }

    suspend fun workerStatusFieldsAsync(seg: MemorySegment): StableAbi.WorkerStatusFields =
        withFfiLimit { StableAbi.workerStatusFields(seg) }

    suspend fun capabilityFieldsAsync(seg: MemorySegment): StableAbi.CapabilityFields =
        withFfiLimit { StableAbi.capabilityFields(seg) }
}
