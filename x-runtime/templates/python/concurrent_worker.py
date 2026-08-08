import sys
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
    params: Optional[Dict[str, Any]] = field(default_factory=dict)
    timeout_ms: Optional[int] = None
    ok: Optional[bool] = None
    result: Optional[Dict[str, Any]] = field(default_factory=dict)
    latency_ms: Optional[int] = None
    error: Optional[Dict[str, Any]] = field(default_factory=dict)
    reload_id: Optional[int] = None
    path: Optional[str] = None
    checksum: Optional[str] = None
    grace_ms: Optional[int] = None

    def to_json(self) -> str:
        data = {k: v for k, v in self.__dict__.items() if v is not None and v != {} and v != []}
        return json.dumps(data) + "\n"

    @classmethod
    def from_json(cls, payload: str) -> "WorkerEnvelope":
        data = json.loads(payload)
        return cls(**{k: data.get(k) for k in cls.__dataclass_fields__.keys() if k in data})


def _send(envelope: WorkerEnvelope):
    sys.stdout.write(envelope.to_json())
    sys.stdout.flush()


def _read() -> WorkerEnvelope:
    line = sys.stdin.readline()
    if not line:
        raise SystemExit(0)
    return WorkerEnvelope.from_json(line)


def main():
    _send(WorkerEnvelope(
        type="handshake",
        worker_id="concurrent-worker",
        worker_type="python",
        capabilities=["task.execute", "reload.request"],
    ))
    ready = _read()
    if ready.type == "shutdown":
        return
    _send(WorkerEnvelope(type="ready", worker_id="concurrent-worker", status="healthy"))

    inflight: Dict[str, threading.Thread] = {}
    while True:
        msg = _read()
        if msg.type == "task.submit":
            def _complete(task_id: str):
                time.sleep(0.05)
                _send(WorkerEnvelope(type="task.result", task_id=task_id, ok=True, result={"echo": msg.params.get("value", "")}, latency_ms=50))
            thread = threading.Thread(target=_complete, args=(msg.task_id,))
            inflight[msg.task_id] = thread
            thread.start()
        elif msg.type == "reload.request":
            _send(WorkerEnvelope(type="reload.completed", reload_id=msg.reload_id, status="active", checksum=msg.checksum or ""))
        elif msg.type == "shutdown":
            for thread in inflight.values():
                thread.join(timeout=2)
            break


if __name__ == "__main__":
    main()
