use std::ffi::c_char;

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct StableAbiManifest {
    pub abi_version_major: u64,
    pub abi_version_minor: u64,
    pub language_host_len: u64,
    pub language_host: *mut c_char,
    pub protocol_version_major: u64,
    pub protocol_version_minor: u64,
    pub capabilities_hot_reload: i32,
    pub capabilities_durable_atomics: i32,
    pub capabilities_capability_tokens: i32,
    pub capabilities_checksum_algorithm_len: u64,
    pub capabilities_checksum_algorithm: *mut c_char,
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct WorkerStatusAbi {
    pub status_code: i32,
    pub reloads_total: u64,
    pub last_reload_success: i32,
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct CapabilityAbi {
    pub granted: i32,
    pub expires_at_ms: u64,
}

#[no_mangle]
pub extern "C" fn stable_abi_manifest_size() -> usize {
    std::mem::size_of::<StableAbiManifest>()
}

#[no_mangle]
pub unsafe extern "C" fn stable_abi_manifest_round_trip(manifest: *mut StableAbiManifest) {
    if manifest.is_null() {
        return;
    }
    unsafe {
        (*manifest).abi_version_major = 1;
        (*manifest).abi_version_minor = 0;
        (*manifest).language_host_len = 0;
        (*manifest).language_host = std::ptr::null_mut();
        (*manifest).protocol_version_major = 1;
        (*manifest).protocol_version_minor = 0;
        (*manifest).capabilities_hot_reload = 1;
        (*manifest).capabilities_durable_atomics = 1;
        (*manifest).capabilities_capability_tokens = 1;
        (*manifest).capabilities_checksum_algorithm_len = 0;
        (*manifest).capabilities_checksum_algorithm = std::ptr::null_mut();
    }
}

#[no_mangle]
pub unsafe extern "C" fn stable_abi_manifest_default(out: *mut StableAbiManifest) {
    stable_abi_manifest_round_trip(out)
}

#[no_mangle]
pub unsafe extern "C" fn stable_abi_worker_status_default(status: *mut WorkerStatusAbi) {
    if status.is_null() {
        return;
    }
    unsafe {
        (*status).status_code = 0;
        (*status).reloads_total = 0;
        (*status).last_reload_success = 0;
    }
}

#[no_mangle]
pub unsafe extern "C" fn stable_abi_capability_default(capability: *mut CapabilityAbi) {
    if capability.is_null() {
        return;
    }
    unsafe {
        (*capability).granted = 0;
        (*capability).expires_at_ms = 0;
    }
}
