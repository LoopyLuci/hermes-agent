"""Auto-generated from x-runtime/protocol/v1/schema/*.json."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EnvelopeError:
    protocol_version: str
    message_id: str
    timestamp: int
    kind: str = field(default="")

@dataclass
class Handshake:
    protocol_version: str
    message_id: str
    timestamp: int
    worker_id: str
    worker_type: str
    capabilities: list[str]
    config: dict[str, Any] = field(default=None)
    abi_version: str = field(default=None)
    language_host: str = field(default=None)
    features: dict[str, Any] = field(default=None)
    kind: str = field(default="handshake")

@dataclass
class Ready:
    protocol_version: str
    message_id: str
    timestamp: int
    worker_id: str
    status: str
    features: list[str]
    kind: str = field(default="ready")

@dataclass
class ReloadCompleted:
    protocol_version: str
    message_id: str
    timestamp: int
    reload_id: int
    status: str
    checksum: str
    kind: str = field(default="reload.completed")

@dataclass
class ReloadRequest:
    protocol_version: str
    message_id: str
    timestamp: int
    reload_id: int
    path: str
    checksum: str
    kind: str = field(default="reload.request")

@dataclass
class Shutdown:
    protocol_version: str
    message_id: str
    timestamp: int
    grace_ms: int
    kind: str = field(default="shutdown")

@dataclass
class TaskResult:
    protocol_version: str
    message_id: str
    timestamp: int
    task_id: str
    ok: bool
    result: dict[str, Any]
    latency_ms: int
    kind: str = field(default="task.result")

@dataclass
class TaskSubmit:
    protocol_version: str
    message_id: str
    timestamp: int
    task_id: str
    method: str
    params: dict[str, Any] = field(default=None)
    timeout_ms: int = field(default=None)
    kind: str = field(default="task.submit")
