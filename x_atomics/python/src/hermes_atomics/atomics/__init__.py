from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class AtomicFileWrite:
    target: Path

    def replace_with(self, payload: bytes) -> Path:
        tmp_name = f".{self.target.name}.{os.getpid()}.tmp"
        tmp_path = self.target.with_name(tmp_name)
        tmp_path.write_bytes(payload)
        tmp_path.replace(self.target)
        return self.target


@dataclass
class AtomicState:
    store: Dict[str, Any] = field(default_factory=dict)

    def put(self, key: str, value: Any) -> None:
        self.store[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.store.get(key, default)

    def compare_swap(self, key: str, expected: Any, new: Any) -> bool:
        current = self.store.get(key)
        if current == expected:
            if new is ...:
                self.store.pop(key, None)
            else:
                self.store[key] = new
            return True
        return False


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class ReloadEvent:
    module: str
    path: Path
    checksum: str
    status: str = "pending"
    reason: Optional[str] = None


@dataclass
class ChecksumStore:
    state: AtomicState = field(default_factory=AtomicState)

    def current(self, module: str) -> Optional[str]:
        return self.state.get(module)

    def update(self, module: str, checksum: str) -> None:
        self.state.put(module, checksum)

    def changed(self, module: str, checksum: str) -> bool:
        previous = self.state.get(module)
        if previous is None:
            self.state.put(module, checksum)
            return False
        changed = previous != checksum
        if changed:
            self.state.put(module, checksum)
        return changed


@dataclass
class ModuleHotReload:
    repo_root: Path
    checksums: ChecksumStore = field(default_factory=ChecksumStore)

    def request(self, module: str, relative_path: str) -> ReloadEvent:
        target = self.repo_root / relative_path
        checksum = sha256_of(target) if target.exists() else ""
        changed = self.checksums.changed(module, checksum)
        event = ReloadEvent(module=module, path=target, checksum=checksum, status="pending" if changed else "noop")
        if changed:
            self.checksums.update(module, checksum)
        return event
