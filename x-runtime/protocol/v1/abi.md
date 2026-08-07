# Stable ABI Manifest Contract

This document describes the versioned native ABI surface exposed by the Rust `hermes_runtime_abi` crate. Host languages bind against this contract to verify runtime capabilities without depending on internal Rust types.

## Library surface

The Rust crate is built as a C-compatible dynamic library:

- `crate-type = ["cdylib", "rlib"]`
- Artifacts: `hermes_runtime_abi.dll` / `libhermes_runtime_abi.so` / `libhermes_runtime_abi.dylib`

## Exported symbols

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `stable_abi_manifest_size` | `size_t stable_abi_manifest_size(void)` | Returns the byte size of `StableAbiManifest` for struct allocation/validation. |
| `stable_abi_manifest_default` | `void stable_abi_manifest_default(_Out_ StableAbiManifest *out)` | Populates the manifest with current ABI/protocol versions and capability flags. |
| `stable_abi_manifest_round_trip` | `void stable_abi_manifest_round_trip(_Out_ StableAbiManifest *out)` | Populates the manifest with known capability values for round-trip testing. |
| `stable_abi_worker_status_default` | `void stable_abi_worker_status_default(_Out_ WorkerStatusAbi *out)` | Zero-initializes worker status struct. |
| `stable_abi_capability_default` | `void stable_abi_capability_default(_Out_ CapabilityAbi *out)` | Zero-initializes capability struct. |

## Struct layout

```c
struct StableAbiCapabilities {
    int32_t hot_reload;
    int32_t durable_atomics;
    int32_t capability_tokens;
    uint64_t checksum_algorithm_len;
    const char *checksum_algorithm;
};

struct StableAbiManifest {
    uint64_t abi_version_major;
    uint64_t abi_version_minor;
    uint64_t language_host_len;
    const char *language_host;
    uint64_t protocol_version_major;
    uint64_t protocol_version_minor;
    struct StableAbiCapabilities capabilities;
};
```

## Expanded stable ABI structs

```c
struct WorkerStatusAbi {
    int32_t status_code;
    uint64_t reloads_total;
    int32_t last_reload_success;
};

struct CapabilityAbi {
    int32_t granted;
    uint64_t expires_at_ms;
};
```

## Host-language binding contract

- Hosts must allocate `StableAbiManifest` using the size returned by `stable_abi_manifest_size`.
- Hosts must pass a pointer to this struct to the out-pointer functions.
- The `_Out_` convention means the function writes into caller-owned memory; the host reads fields after the call returns.
- Pointer fields (`language_host`, `checksum_algorithm`) point to static NUL-terminated string literals owned by the Rust library. Hosts must not free them.

## Versioning

- Breaking struct layout changes increment `abi_version_major`.
- Backward-compatible capability additions increment `abi_version_minor`.
- Every manifest carries both ABI and protocol versions so hosts can detect mismatches before binding.
- ABI major version mismatches must disable the x-runtime runtime instead of attempting to bind.
- Capability flags must be `0` or `1`; any other value is treated as a mismatch.

## Verified host tests

- Python: `tests/x-runtime/test_stable_abi_ffi.py` using `ctypes`
- TypeScript/Node: `x-runtime/templates/typescript/tests/stable_abi.test.ts` using `koffi`
- Clojure/Java: `x-runtime/clojure/test/hermes/StableAbiTest.java` using Java Foreign Function API
- Kotlin/JVM: `x-runtime/kotlin/src/jvmTest/kotlin/hermes/abi/StableAbiTest.kt` and `CapabilityFlowTest.kt` using Java Foreign Function API

## Hot-reload protocol invariants

The reload protocol depends on atomicity across these invariants:

1. Checksum verification: `reload.request` must include a non-empty `checksum`; the host must verify source integrity before applying any replacement.
2. Atomic swap: `reload.completed` must be emitted only after the new worker image is loaded and ready to serve; intermediate states must remain opaque to clients.
3. Rollback path: if the new worker fails to emit `ready` within `reload_timeout`, the supervisor must mark the worker `Error` and keep the previous binary/state intact.
4. Capability continuity: capability tokens remain valid across reload unless explicitly revoked; expired tokens are purged only during `assert_authorized` or `renew_capabilities`.

## Windows CI

```powershell
cd D:\Projects\HermesAgentExpansion\x-runtime\clojure\test\hermes
javac StableAbiTest.java
java --enable-native-access=ALL-UNNAMED StableAbiTest
```
