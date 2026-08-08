# hermes-atomics

Python-facing durable atomic primitives for the Hermes expansion runtime.

- Atomic file writes with fsync-backed durability.
- Append-only WAL state for crash recovery.
- Bridges Rust durability guarantees into Python orchestration paths.

Install editable:
`pip install -e x_atomics/python`
