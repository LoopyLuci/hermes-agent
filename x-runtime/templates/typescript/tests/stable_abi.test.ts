import { test, describe } from 'node:test';
import assert from 'node:assert';
import koffi from 'koffi';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '../../../..');

const dllPath = path.join(repoRoot, 'x-runtime', 'rust', 'target', 'release', 'hermes_runtime_abi.dll');
const lib = koffi.load(dllPath);

const StableAbiManifest = koffi.struct('StableAbiManifest', {
  abi_version_major: 'uint64',
  abi_version_minor: 'uint64',
  language_host_len: 'uint64',
  language_host: 'string',
  protocol_version_major: 'uint64',
  protocol_version_minor: 'uint64',
  capabilities_hot_reload: 'int32',
  capabilities_durable_atomics: 'int32',
  capabilities_capability_tokens: 'int32',
  capabilities_checksum_algorithm_len: 'uint64',
  capabilities_checksum_algorithm: 'string',
});

const WorkerStatusAbi = koffi.struct('WorkerStatusAbi', {
  status_code: 'int32',
  reloads_total: 'uint64',
  last_reload_success: 'int32',
});

const CapabilityAbi = koffi.struct('CapabilityAbi', {
  granted: 'int32',
  expires_at_ms: 'uint64',
});

const stable_abi_manifest_size = lib.func('size_t stable_abi_manifest_size(void)');
const stable_abi_manifest_default = lib.func('void stable_abi_manifest_default(_Out_ StableAbiManifest *out)');
const stable_abi_manifest_round_trip = lib.func('void stable_abi_manifest_round_trip(_Out_ StableAbiManifest *out)');
const stable_abi_worker_status_default = lib.func('void stable_abi_worker_status_default(_Out_ WorkerStatusAbi *out)');
const stable_abi_capability_default = lib.func('void stable_abi_capability_default(_Out_ CapabilityAbi *out)');

describe('Stable ABI/FFI binding (TypeScript via koffi)', () => {
  test('manifest size matches struct layout', () => {
    const size = stable_abi_manifest_size();
    assert.strictEqual(size, koffi.sizeof(StableAbiManifest));
  });

  test('default manifest is zeroed', () => {
    const manifest = {};
    stable_abi_manifest_default(manifest);
    assert.strictEqual(manifest.abi_version_major, 0);
    assert.strictEqual(manifest.abi_version_minor, 0);
    assert.strictEqual(manifest.capabilities_hot_reload, 0);
    assert.strictEqual(manifest.language_host, null);
  });

  test('round-trip manifest values through out-pointer', () => {
    const manifest = {};
    stable_abi_manifest_round_trip(manifest);
    assert.strictEqual(manifest.abi_version_major, 1);
    assert.strictEqual(manifest.abi_version_minor, 0);
    assert.strictEqual(manifest.protocol_version_major, 1);
    assert.strictEqual(manifest.protocol_version_minor, 0);
    assert.strictEqual(manifest.capabilities_hot_reload, 1);
    assert.strictEqual(manifest.capabilities_durable_atomics, 1);
    assert.strictEqual(manifest.capabilities_capability_tokens, 1);
    assert.strictEqual(manifest.language_host, 'test');
    assert.strictEqual(manifest.capabilities_checksum_algorithm, 'sha256');
  });

  test('default worker status is zeroed', () => {
    const status = {};
    stable_abi_worker_status_default(status);
    assert.strictEqual(status.status_code, 0);
    assert.strictEqual(status.reloads_total, 0);
    assert.strictEqual(status.last_reload_success, 0);
  });

  test('default capability is zeroed', () => {
    const capability = {};
    stable_abi_capability_default(capability);
    assert.strictEqual(capability.granted, 0);
    assert.strictEqual(capability.expires_at_ms, 0);
  });
});
