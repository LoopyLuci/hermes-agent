# Hermes Multi-Language Worker Protocol
## Version 1.0 — Stable Contract

This directory defines the **only** stable interface between the Hermes supervisor
and any worker, in any language, past or future.

### Design Principles
- **Language-agnostic:** Workers are black boxes. The supervisor never inspects worker internals.
- **Transport-agnostic:** v1 defines stdio NDJSON. Future versions may add HTTP/2, shared memory, or RPC.
- **Versioned:** Every envelope includes `protocol_version`. Breaking changes increment the version.
- **Stateless handshake:** Workers can be restarted at any time without supervisor state loss.
- **Capability-based:** Workers receive opaque capability tokens. They cannot acquire new capabilities without supervisor grant.

---

## Transport: stdio NDJSON

Each message is a single JSON object terminated by `\n` on stdout.
Errors are written to stderr, also NDJSON, prefixed with `stderr: ` for clarity.

Frame format:
```
{<json object>}\n
```

No framing headers, no chunked encoding. UTF-8 only.

---

## Schema and Code Generation

- Canonical JSON Schemas live in `schema/`.
- Rust structs and Python dataclasses must be generated or validated against these schemas in CI.
- All envelope types include `protocol_version`, `message_id`, `timestamp`, and `type`.

---

## Message Envelopes

All messages share this base:
```json
{
  "protocol_version": "1.0",
  "message_id": "uuid",
  "timestamp": 1700000000000,
  "type": "handshake|ready|error|heartbeat|task.submit|task.result|reload.request|reload.started|reload.completed|reload.failed|shutdown|capability.grant"
}
```

### Handshake (supervisor → worker on spawn)
```json
{
  "protocol_version": "1.0",
  "message_id": "...",
  "timestamp": 1700000000000,
  "type": "handshake",
  "worker_id": "rust-atomic-1",
  "worker_type": "rust",
  "capabilities": ["atomic.state", "task.execute", "hot.reload"],
  "config": {"log_level": "info"}
}
```

### Ready (worker → supervisor)
```json
{
  "protocol_version": "1.0",
  "message_id": "...",
  "timestamp": 1700000000000,
  "type": "ready",
  "worker_id": "rust-atomic-1",
  "status": "healthy",
  "features": ["atomic.compare_swap", "task.stream"]
}
```

### Task Submit (supervisor → worker)
```json
{
  "protocol_version": "1.0",
  "message_id": "...",
  "timestamp": 1700000000000,
  "type": "task.submit",
  "task_id": "task-abc",
  "method": "atomic.put",
  "params": {"key": "mode", "value": "agentic"},
  "timeout_ms": 5000
}
```

### Task Result (worker → supervisor)
```json
{
  "protocol_version": "1.0",
  "message_id": "...",
  "timestamp": 1700000000000,
  "type": "task.result",
  "task_id": "task-abc",
  "ok": true,
  "result": {"status": "ok"},
  "latency_ms": 2
}
```

### Reload Request (supervisor → worker)
```json
{
  "protocol_version": "1.0",
  "message_id": "...",
  "timestamp": 1700000000000,
  "type": "reload.request",
  "reload_id": 42,
  "path": "/workers/rust/atomic/src/lib.rs",
  "checksum": "sha256:..."
}
```

### Reload Completed (worker → supervisor)
```json
{
  "protocol_version": "1.0",
  "message_id": "...",
  "timestamp": 1700000000000,
  "type": "reload.completed",
  "reload_id": 42,
  "status": "active",
  "checksum": "sha256:..."
}
```

### Shutdown (supervisor → worker)
```json
{
  "protocol_version": "1.0",
  "message_id": "...",
  "timestamp": 1700000000000,
  "type": "shutdown",
  "grace_ms": 5000
}
```

---

## Worker Implementation Contract

To add a new language runtime, implement this interface:

1. **Spawn** reads the handshake from stdin, acknowledges with `ready`, and advertises ABI capabilities.
2. **Dispatch** reads messages from stdin, processes them, writes responses to stdout.
3. **Heartbeat** emits a `heartbeat` message every 30s with worker status.
4. **Shutdown** exits cleanly on `shutdown` or EOF.
5. **Reload** supports `reload.request` with in-place code swap and state migration.
6. **Error handling** writes NDJSON error objects to stderr, never crashes silently.

### ABI/portability contract

Future language hosts should preserve these guarantees:

- **Protocol versioned:** Every envelope includes `protocol_version`. Additive schema extensions must be optional and backwards compatible.
- **Capability advertisement:** Workers advertise exact capabilities in handshake `features`/`config` or language-specific extensions. Do not assume implicit capability availability.
- **Stable transport core:** The core supervisor-to-worker contract remains stdio NDJSON unless a new protocol version is published.
- **Checksum algorithm declared:** If a host supports hot reload, it must declare its checksum algorithm. Supervisors must not hardcode one algorithm across all hosts.
- **No shared ABI linkage for core protocol:** Core protocol messages are serialized JSON. FFI/ABI boundaries may exist for performance hot paths, but they must never be required for correctness.

---

## Future Versions

- **v2:** Add HTTP/2 transport for workers that need binary streaming.
- **v3:** Add shared-memory transport for zero-copy data transfer.
- **v4:** Add capability revocation and worker migration.

All versions coexist. The supervisor matches `protocol_version` and falls back to compatible older versions.
