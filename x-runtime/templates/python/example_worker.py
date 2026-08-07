"""Example Python worker implementing Hermes worker protocol v1."""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import time
from pathlib import Path

from hermes_worker.protocol import (
    HandshakeMessage,
    ReadyMessage,
    ReloadRequestMessage,
    ShutdownMessage,
    TaskSubmitMessage,
    WorkerEnvelope,
    WorkerTransport,
)


class ExampleWorker:
    def __init__(self, worker_id: str) -> None:
        self.worker_id = worker_id
        self.transport = WorkerTransport()
        self.running = True
        self.reload_dir = Path(tempfile.gettempdir()) / "hermes-worker-reloads"
        self.reload_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> None:
        self.transport.write(WorkerEnvelope(
            type="ready",
            worker_id=self.worker_id,
            status="healthy",
            features=["task.echo"],
        ))
        while self.running:
            envelope = self.transport.read()
            self.handle(envelope)

    def handle(self, envelope: WorkerEnvelope) -> None:
        kind = envelope.type
        if kind == "task.submit":
            self.on_task(envelope)
        elif kind == "reload.request":
            self.on_reload(envelope)
        elif kind == "shutdown":
            self.on_shutdown(envelope)
        else:
            self.transport.write(WorkerEnvelope(type="error", error={"code": "unknown", "message": f"unknown type {kind}"}))

    def on_task(self, envelope: WorkerEnvelope) -> None:
        result = {"echo": envelope.params}
        self.transport.write(WorkerEnvelope(type="task.result", task_id=envelope.task_id, ok=True, result=result, latency_ms=1))

    def _checksum(self, path: Path) -> str:
        if not path.exists():
            return ""
        digest = hashlib.md5(path.read_bytes()).hexdigest()
        return digest

    def _validate(self, path: Path) -> bool:
        if not path.exists():
            return False
        try:
            compile(path.read_text(encoding="utf-8"), path.name, "exec")
        except SyntaxError:
            return False
        return True

    def _shadow_apply(self, source_path: str, new_content: bytes) -> tuple[Path, str]:
        target = Path(source_path)
        shadow = self.reload_dir / f"{target.name}.reload-{int(time.time() * 1000)}.py"
        shadow.write_bytes(new_content)
        checksum = self._checksum(shadow)
        return shadow, checksum

    def on_reload(self, envelope: WorkerEnvelope) -> None:
        reload_id = envelope.reload_id or 0
        path = envelope.path or ""
        checksum = envelope.checksum or ""
        status = "failed"
        reason = ""

        try:
            if not path or not checksum:
                raise ValueError("missing path or checksum")

            source = Path(path)
            if not source.exists():
                raise FileNotFoundError(f"missing {source}")

            current = self._checksum(source)
            if current == checksum:
                status = "completed"
                self.transport.write(WorkerEnvelope(
                    type="reload.completed",
                    reload_id=reload_id,
                    status=status,
                    checksum=checksum,
                ))
                return

            new_content = source.read_bytes()
            shadow, new_checksum = self._shadow_apply(path, new_content)
            if not self._validate(shadow):
                raise ValueError("shadow validation failed")

            tmp = source.with_suffix(".tmp")
            tmp.write_bytes(new_content)
            tmp.replace(source)

            status = "completed"
        except Exception as exc:
            status = "failed"
            reason = str(exc)

        try:
            self.transport.write(WorkerEnvelope(
                type="reload.completed",
                reload_id=reload_id,
                status=status,
                checksum=checksum if status == "completed" else "",
                error={"message": reason} if reason else None,
            ))
        except Exception:
            pass

    def on_shutdown(self, envelope: WorkerEnvelope) -> None:
        self.running = False
        time.sleep(0)
        raise SystemExit(0)


def main() -> None:
    handshake = WorkerTransport().read()
    worker = ExampleWorker(handshake.worker_id or "python-worker")
    worker.run()


if __name__ == "__main__":
    main()
