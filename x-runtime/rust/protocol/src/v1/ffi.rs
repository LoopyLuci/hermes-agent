/// Stable FFI metadata for cross-language binding tests.
/// 
/// Safe Rust callers should use the native `AbiManifest` types; this shim exists
/// for verification via `ctypes`/`cdylib` binding tests only.
#[repr(C)]
#[derive(Debug, Clone, Copy, Default)]
pub struct FfiAbiFlags {
    pub abi_version_major: u32,
    pub abi_version_minor: u32,
    pub hot_reload: u32,
    pub durable_atomics: u32,
    pub capability_tokens: u32,
    pub checksum_algorithm: u32,
}

impl From<AbiManifest> for FfiAbiFlags {
    fn from(value: AbiManifest) -> Self {
        let mut flags = Self::default();
        let versions: Vec<u32> = value
            .abi_version
            .split('.')
            .filter_map(|part| part.parse::<u32>().ok())
            .collect();
        if versions.len() >= 2 {
            flags.abi_version_major = versions[0];
            flags.abi_version_minor = versions[1];
        }
        flags.hot_reload = u32::from(value.capabilities.hot_reload);
        flags.durable_atomics = u32::from(value.capabilities.durable_atomics);
        flags.capability_tokens = u32::from(value.capabilities.capability_tokens);
        flags
    }
}
