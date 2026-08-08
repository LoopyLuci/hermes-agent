"""Malformed-input tolerant worker for supervisor e2e tests."""
from __future__ import annotations

import json
import sys


def _write(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = msg.get("type")
        if kind == "handshake":
            _write({
                "protocol_version": "1.0",
                "message_id": msg.get("message_id", ""),
                "timestamp": 0,
                "type": "ready",
                "worker_id": msg.get("worker_id", "malformed-worker"),
                "status": "healthy",
                "features": {}
            })
        elif kind == "task.submit":
            _write({
                "protocol_version": "1.0",
                "message_id": msg.get("message_id", ""),
                "timestamp": 0,
                "type": "task.result",
                "task_id": msg.get("task_id", ""),
                "ok": True,
                "result": {},
                "latency_ms": 0,
            })
        else:
            _write({
                "protocol_version": "1.0",
                "message_id": msg.get("message_id", ""),
                "timestamp": 0,
                "type": "ready",
                "worker_id": msg.get("worker_id", "malformed-worker"),
                "status": "healthy",
                "features": {}
            })


if __name__ == "__main__":
    main()
