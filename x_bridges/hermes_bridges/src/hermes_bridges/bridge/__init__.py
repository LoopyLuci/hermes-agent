from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_bridges.bridge import hot_reload_watcher


@dataclass
class BridgeSettings:
    repo_root: Path
    atomic_module_dir: Path
    runtime_workers: Dict[str, str] = field(default_factory=dict)


@dataclass
class BridgeResult:
    ok: bool
    status: str
    detail: str
    payload: Dict[str, Any] | None = None


class LanguageBridge:
    def __init__(self, settings: BridgeSettings) -> None:
        self.settings = settings

    def status(self) -> Dict[str, Dict[str, str]]:
        raise NotImplementedError

    def apply_hot_reload(self, module_name: str, target: Path) -> BridgeResult:
        raise NotImplementedError


class RustBridge(LanguageBridge):
    def status(self) -> Dict[str, Dict[str, str]]:
        cargo = shutil.which("cargo")
        lib = self.settings.atomic_module_dir / "libhermes_runtime_atomic.so"
        return {
            "rust": {
                "binary": cargo or "missing",
                "atomic_lib": str(lib) if lib.exists() else "missing",
            }
        }

    def apply_hot_reload(self, module_name: str, target: Path) -> BridgeResult:
        cargo = shutil.which("cargo")
        if not cargo:
            return BridgeResult(False, "error", "cargo not found")
        manifest = self.settings.repo_root / "x-runtime" / "rust" / "atomic" / "Cargo.toml"
        if not manifest.exists():
            return BridgeResult(False, "error", f"missing manifest: {manifest}")
        try:
            cmd = [cargo, "build", "-p", "hermes-runtime-atomic", "--release"]
            subprocess.run(cmd, cwd=manifest.parent, check=True, capture_output=True, text=True)
            built = self._resolve_lib(manifest.parent)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(built, target)
            checksum = hot_reload_watcher.checksum_of(target)
            return BridgeResult(True, "reloaded", str(target), {"checksum": checksum})
        except subprocess.CalledProcessError as exc:
            return BridgeResult(False, "error", exc.stderr or str(exc))

    def _resolve_lib(self, crate_dir: Path) -> Path:
        target_dir = crate_dir / "target" / "release"
        if sys.platform == "win32":
            candidates = list(target_dir.glob("*.dll"))
        elif sys.platform == "darwin":
            candidates = list(target_dir.glob("*.dylib"))
        else:
            candidates = list(target_dir.glob("lib*.so"))
        if not candidates:
            raise FileNotFoundError(f"no built library found in {target_dir}")
        return candidates[0]


class ClojureBridge(LanguageBridge):
    def status(self) -> Dict[str, Dict[str, str]]:
        clj = shutil.which("clojure")
        return {
            "clojure": {
                "binary": clj or "missing",
                "source": str(self.settings.repo_root / "x-runtime" / "clojure" / "src" / "hermes"),
            }
        }

    def apply_hot_reload(self, module_name: str, target: Path) -> BridgeResult:
        # Clojure hot reload is data-oriented: write a reload manifest and
        # let the consumer side reload from source/classpath. We keep this
        # as a soft reload marker because live JVM reload semantics are
        # module-specific and best handled by the Clojure runtime itself.
        manifest = target.parent / f"{target.name}.json"
        manifest.write_text(json.dumps({"module": module_name, "target": str(target), "action": "reload"}, indent=2), encoding="utf-8")
        return BridgeResult(True, "reload_marker", str(manifest))


class TypeScriptBridge(LanguageBridge):
    def status(self) -> Dict[str, Dict[str, str]]:
        node = shutil.which("node")
        npm = shutil.which("npm")
        return {
            "typescript": {
                "node": node or "missing",
                "npm": npm or "missing",
                "source": str(self.settings.repo_root / "x-runtime" / "typescript" / "src"),
            }
        }

    def apply_hot_reload(self, module_name: str, target: Path) -> BridgeResult:
        return BridgeResult(True, "reload_marker", str(target))


class BridgeManager:
    def __init__(self, settings: BridgeSettings) -> None:
        self.settings = settings
        self.bridges: List[LanguageBridge] = [
            RustBridge(settings),
            ClojureBridge(settings),
            TypeScriptBridge(settings),
        ]

    def status(self) -> Dict[str, Dict[str, str]]:
        result: Dict[str, Dict[str, str]] = {}
        for bridge in self.bridges:
            result.update(bridge.status())
        return result

    def apply_hot_reload(self, module_name: str, target: Path) -> Dict[str, BridgeResult]:
        return {type(bridge).__name__: bridge.apply_hot_reload(module_name, target) for bridge in self.bridges}

    def atomic_runtime_path(self) -> Optional[Path]:
        return hot_reload_watcher.best_atomic_lib(self.settings.repo_root)
