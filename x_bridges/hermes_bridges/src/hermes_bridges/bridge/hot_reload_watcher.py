"""Hot-reload watcher for Hermes Agent expansion.

This module watches specified paths and emits reload events when file
checksums change. It is used by the multi-language runtime to coordinate
atomic and hot reload capabilities across Python, Rust, Clojure, and
TypeScript workers.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional


@dataclass
class ReloadEvent:
    path: Path
    checksum: str
    previous_checksum: Optional[str] = None


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


class HotReloadWatcher:
    def __init__(self) -> None:
        self._checksums: Dict[Path, str] = {}
        self._lock = threading.Lock()
        self._listeners: list[Callable[[ReloadEvent], None]] = []

    def watch(self, path: Path, on_change: Optional[Callable[[ReloadEvent], None]] = None) -> None:
        path = Path(path)
        if not path.exists():
            return
        current = sha256_of(path)
        with self._lock:
            previous = self._checksums.get(path)
            self._checksums[path] = current
        if previous is not None and previous != current:
            event = ReloadEvent(path=path, checksum=current, previous_checksum=previous)
            self._emit(event)
            if on_change is not None:
                on_change(event)

    def add_listener(self, listener: Callable[[ReloadEvent], None]) -> None:
        self._listeners.append(listener)

    def _emit(self, event: ReloadEvent) -> None:
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception:
                continue
