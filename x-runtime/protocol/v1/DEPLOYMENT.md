# x-runtime Deployment Contract

This document defines the operational contract for the Hermes x-runtime supervisor,
cross-language ABI, and bridge integration. It is intended for operators and future
maintainers who need to upgrade, roll back, or diagnose production deployments.

## Supervisor Binary Layout

The supervisor is distributed as a single Rust binary: `hermes-runtime-supervisor`.

```
target/release/hermes-runtime-supervisor[.exe]
  - HTTP API:
      GET /v1/status
      GET /v1/healthz
      POST /v1/workers
      GET /v1/workers/{id}
      POST /v1/workers/{id}/reload
      POST /v1/workers/{id}/shutdown
  - Persistent state: <bind-addr-hash>.json
  - Child stdio: newline-delimited JSON or versioned binary frames
```

Recommended deployment:
1. Build with `cargo build --release -p hermes-runtime-supervisor`.
2. Place the binary in a versioned release directory, e.g. `/opt/hermes/x-runtime/<version>/`.
3. Symlink `/opt/hermes/x-runtime/current` to the active version.
4. Run under a process supervisor with respawn and log capture.

## Capability Token TTL Semantics

- Tokens are issued on worker spawn.
- Default TTL: 60 seconds from issuance.
- Tokens are renewable via `POST /workers/{id}/capabilities/renew`.
- Expired tokens are rejected by capability checks until renewed.
- Tokens are invalidated when a worker is stopped or reloaded.

## Hot-Reload State Machine

States: `idle -> reload_requested -> in_progress -> completed | failed`.

- `reload_requested`: supervisor sends `reload.request` envelope to worker.
- `in_progress`: worker MAY respond with `reload.started`.
- `completed`: worker responds with `reload.completed`.
- `failed`: worker responds with `reload.failed` or times out.
- Rollback: operator may send `reload.rollback`; worker should return to previous build.

## Rollback Behavior

Rollback is a first-class operation, not an error recovery path.

- Operator sends `POST /workers/{id}/reload` with `{"reload_id": <prev>, "action": "rollback"}`.
- Supervisor marks reload state as `rolled_back`.
- Worker restores previous binary/runtime state.
- Capability tokens are NOT renewed during rollback; stale tokens remain invalid.
- Health checks must pass before the worker returns to `healthy` status.

## Bridge Integration Contract

The Hermes CLI/Python bridge must:
1. Check `x_runtime.enabled` before any dispatch.
2. Resolve `endpoint` from config or explicit init arg.
3. Load the ABI DLL from `x-runtime/rust/target/release/hermes_runtime_abi.dll`.
4. Reject mismatched ABI major versions with `XRuntimeBridgeAbiMismatch`.
5. Apply circuit-breaker semantics after 3 consecutive failures; half-open after 30s.
6. Timeout requests at 2s by default; configurable via `request_timeout`.

## Operator Runbooks

### Capability TTL Renewal

1. Call `POST /workers/{id}/capabilities/renew` before token expiry.
2. Monitor `GET /status` for `workers` and inspect worker `status`.
3. If a worker returns `degraded`, check `backoff_triggered` in metrics and
   inspect worker stderr/stdout logs.
4. Manual restart path: `POST /workers/{id}/shutdown`, then `POST /workers` with
   the original `WorkerSpec`.

### ABI Mismatch Recovery

1. Build a fresh ABI DLL: `cargo build --release -p hermes-runtime-abi`.
2. Replace `x-runtime/rust/target/release/hermes_runtime_abi.dll`.
3. Restart Hermes CLI or reload the bridge.
4. If the mismatch persists, disable x-runtime in `config.yaml` (`x_runtime.enabled: false`)
   to revert to default Python behavior without losing main-session state.

### Supervisor Binary Upgrade

1. Build new binary: `cargo build --release -p hermes-runtime-supervisor`.
2. Update symlink `/opt/hermes/x-runtime/current` to new version directory.
3. Send `POST /workers/{id}/reload` to each worker with new checksum and path.
4. Confirm health with `GET /healthz` before draining old process.
5. Rollback: point symlink to previous version and re-run worker reload with rollback action.

## Cross-Language Compatibility

- ABI major version is encoded at offset 0..8 of the manifest struct.
- ABI minor version is encoded at offset 8..16.
- All hosts must treat a major version mismatch as hard failure.
- Minor version mismatch is logged but allowed unless explicitly restricted.

## Observability Hooks

Supervisor emits events for:
- worker spawn, shutdown, restart, backoff
- capability grant, deny, renew, expire
- transport send, receive, drop
- reload request, start, complete, fail, rollback

Operators should wire these into their metrics/alerting stack.

## Linux CI Validation

- Use `ubuntu-latest` GitHub Actions runner.
- Cache Kotlin compiler at `/opt/kotlin/kotlinc`.
- Cache Rust cargo registry and target directories.
- Build ABI DLL, run supervisor/core/protocol tests, TypeScript tests, Python tests, Kotlin tests.
- All jobs must pass before merge.

## Versioning Policy

- Supervisor HTTP API is versioned by path prefix: `/v1/...`
- ABI uses major/minor semantics with a manifest struct.
- Binary frames use `version: u16` header field.
- Protocol envelopes require `protocol_version: "1.0"`.
