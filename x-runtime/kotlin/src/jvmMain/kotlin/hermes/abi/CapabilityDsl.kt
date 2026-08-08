package hermes.abi

import java.lang.foreign.*

data class CapabilityGrant(
    val granted: Long,
    val expiresAtMs: Long
) {
    companion object {
        fun default(): CapabilityGrant {
            val bytes = stable_abi_capability_default()
            return CapabilityGrant(
                granted = bytes.getAtIndex(ValueLayout.JAVA_INT, 0).toLong(),
                expiresAtMs = bytes.getAtIndex(ValueLayout.JAVA_LONG, 1)
            )
        }
    }

    fun healthy(): Boolean = granted >= 0L && expiresAtMs > 0L
}

class CapabilityDsl(private val grant: CapabilityGrant) {
    fun validate(block: CapabilityGrant.() -> Boolean): Boolean = block(grant)
}

fun capabilityValidate(block: CapabilityGrant.() -> Boolean): Boolean {
    val grant = CapabilityGrant.default()
    return CapabilityDsl(grant).validate(block)
}
