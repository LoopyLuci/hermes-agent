from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class HandshakeMessage:
    protocol_version: str = "1.0"
    message_id: str = ""
    timestamp: int = 0
    type: str = "handshake"
    worker_id: str = ""
    worker_type: str = "python"
    capabilities: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReadyMessage:
    protocol_version: str = "1.0"
    message_id: str = ""
    timestamp: int = 0
    type: str = "ready"
    worker_id: str = ""
    status: str = "healthy"
    features: List[str] = field(default_factory=list)


@dataclass
class TaskSubmitMessage:
    protocol_version: str = "1.0"
    message_id: str = ""
    timestamp: int = 0
    type: str = "task.submit"
    task_id: str = ""
    method: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    timeout_ms: Optional[int] = None


@dataclass
class TaskResultMessage:
    protocol_version: str = "1.0"
    message_id: str = ""
    timestamp: int = 0
    type: str = "task.result"
    task_id: str = ""
    ok: bool = True
    result: Dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0


@dataclass
class ReloadRequestMessage:
    protocol_version: str = "1.0"
    message_id: str = ""
    timestamp: int = 0
    type: str = "reload.request"
    reload_id: int = 0
    path: str = ""
    checksum: str = ""


@dataclass
class ReloadCompletedMessage:
    protocol_version: str = "1.0"
    message_id: str = ""
    timestamp: int = 0
    type: str = "reload.completed"
    reload_id: int = 0
    status: str = "active"
    checksum: str = ""


@dataclass
class ShutdownMessage:
    protocol_version: str = "1.0"
    message_id: str = ""
    timestamp: int = 0
    type: str = "shutdown"
    grace_ms: int = 5000


@dataclass
class WorkerEnvelope:
    protocol_version: str = "1.0"
    message_id: str = ""
    timestamp: int = 0
    type: str = ""
    worker_id: Optional[str] = None
    worker_type: Optional[str] = None
    capabilities: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    features: Optional[List[str]] = None
    task_id: Optional[str] = None
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    timeout_ms: Optional[int] = None
    ok: Optional[bool] = None
    result: Optional[Dict[str, Any]] = None
    latency_ms: Optional[int] = None
    error: Optional[Dict[str, Any]] = None
    reload_id: Optional[int] = None
    path: Optional[str] = None
    checksum: Optional[str] = None
    grace_ms: Optional[int] = None

    def to_json(self) -> str:
        data = {k: v for k, v in self.__dict__.items() if v is not None}
        return json.dumps(data) + "\n"

    @classmethod
    def from_json(cls, payload: str) -> "WorkerEnvelope":
        data = json.loads(payload)
        return cls(**{k: data.get(k) for k in cls.__dataclass_fields__.keys() if k in data})


class WorkerTransport:
    def __init__(self, stdin=None, stdout=None, endpoint: Optional[str] = None) -> None:
        self.stdin = stdin if stdin is not None else sys.stdin
        self.stdout = stdout if stdout is not None else sys.stdout
        self.endpoint = (endpoint or "").strip() or None

    def read(self) -> WorkerEnvelope:
        line = self.stdin.readline()
        if not line:
            raise SystemExit(0)
        return WorkerEnvelope.from_json(line)

    def write(self, envelope: WorkerEnvelope) -> None:
        self.stdout.write(envelope.to_json())
        self.stdout.flush()

    def invoke_tool(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a tool invocation to a remote x-runtime worker endpoint.

        Returns the parsed JSON response body. When no endpoint is configured,
        falls back to an encoded local result so callers can remain agnostic
        about transport.
        """
        if not self.endpoint:
            return {"ok": True, "result": payload}

        try:
            import urllib.request
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.endpoint,
                data=data,
                headers={"content-type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                raw = response.read().decode("utf-8")
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
                return {"ok": True, "result": parsed}
        except Exception as exc:
            return {"ok": False, "error": {"message": str(exc), "type": type(exc).__name__}}
