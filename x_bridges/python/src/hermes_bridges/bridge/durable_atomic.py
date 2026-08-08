"""Durable atomic state with write-ahead log, exposed to Python."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class WalEntry:
    key: str = ""
    prev: Optional[Any] = None
    next: Optional[Any] = None
    checksum: str = ""
    timestamp: int = 0

    def to_json(self) -> str:
        return json.dumps({
            "key": self.key,
            "prev": self.prev,
            "next": self.next,
            "checksum": self.checksum,
            "timestamp": self.timestamp,
        })

    @classmethod
    def from_json(cls, payload: str) -> "WalEntry":
        data = json.loads(payload)
        return cls(
            key=data.get("key", ""),
            prev=data.get("prev"),
            next=data.get("next"),
            checksum=data.get("checksum", ""),
            timestamp=data.get("timestamp", 0),
        )


class DurableAtomicState:
    def __init__(self, wal_path: str | Path) -> None:
        self.wal_path = Path(wal_path)
        self.state: Dict[str, Any] = {}
        self.wal: list[WalEntry] = []
        self._recover()

    def _recover(self) -> None:
        if not self.wal_path.exists():
            return
        lines = self.wal_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            if not line.strip():
                continue
            try:
                entry = WalEntry.from_json(line)
            except Exception:
                continue
            self.wal.append(entry)
            if entry.next is not None:
                self.state[entry.key] = entry.next
            else:
                self.state.pop(entry.key, None)

    def _append(self, entry: WalEntry) -> None:
        self.wal.append(entry)
        self.wal_path.parent.mkdir(parents=True, exist_ok=True)
        with self.wal_path.open("a", encoding="utf-8") as handle:
            handle.write(entry.to_json() + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def put(self, key: str, value: Any) -> None:
        entry = WalEntry(
            key=key,
            prev=self.state.get(key),
            next=value,
            checksum=self._checksum(key, value),
            timestamp=self._now_ms(),
        )
        self.state[key] = value
        self._append(entry)

    def compare_swap(self, key: str, expected: Optional[Any], new: Optional[Any]) -> bool:
        current = self.state.get(key)
        if current != expected:
            return False
        entry = WalEntry(
            key=key,
            prev=current,
            next=new,
            checksum=self._checksum(key, new),
            timestamp=self._now_ms(),
        )
        if new is not None:
            self.state[key] = new
        else:
            self.state.pop(key, None)
        self._append(entry)
        return True

    def get(self, key: str) -> Optional[Any]:
        return self.state.get(key)

    def checkpoint(self, snapshot_path: str | Path) -> None:
        snapshot = {
            "state": self.state,
            "checksum": "",
            "timestamp": self._now_ms(),
        }
        target = Path(snapshot_path)
        temp = target.with_suffix(".tmp")
        temp.write_text(json.dumps(snapshot), encoding="utf-8")
        temp.replace(target)

    @staticmethod
    def _checksum(key: str, value: Any) -> str:
        payload = f"{key}:{json.dumps(value, sort_keys=True)}"
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _now_ms() -> int:
        import time
        return int(time.time() * 1000)
