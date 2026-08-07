package hermes.abi

import java.lang.foreign.*

data class HotReloadStatus(
    val supported: Boolean,
    val durableAtomics: Boolean,
    val capabilityTokens: Boolean
) {
    companion object {
        fun current(): HotReloadStatus {
            val bytes = stable_abi_manifest_default()
            return HotReloadStatus(
                supported = bytes.getAtIndex(ValueLayout.JAVA_INT, 12) == 1,
                durableAtomics = bytes.getAtIndex(ValueLayout.JAVA_INT, 13) == 1,
                capabilityTokens = bytes.getAtIndex(ValueLayout.JAVA_INT, 14) == 1
            )
        }
    }

    fun healthy(): Boolean = supported && durableAtomics && capabilityTokens
}

object HotReloadChecker {
    fun canHotReload(): Boolean = HotReloadStatus.current().healthy()
}
