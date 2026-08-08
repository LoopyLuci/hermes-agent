"""Self-improvement loop for Hermes Agent expansion.

This module provides a configurable loop that can inspect Hermes modules,
propose improvements, and apply them via atomic writes. It is designed to
be language-agnostic and work with Python, Rust, Clojure, and TypeScript.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from hermes_bridges.bridge.durable_atomic import DurableAtomicState, WalEntry

from .mutator import Mutator


class LoopState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class LoopConfig:
    repo_root: Path
    watch_paths: List[Path] = field(default_factory=list)
    max_workers: int = 4
    apply_requires_approval: bool = True
    allowed_languages: List[str] = field(default_factory=lambda: ["python", "rust", "clojure", "typescript"])
    durable_bridge_path: Optional[Path] = None


@dataclass
class ImprovementProposal:
    id: str
    module: str
    language: str
    description: str
    patch: str
    risk: str
    checksum_before: Optional[str] = None
    checksum_after: Optional[str] = None
    original_content_hex: Optional[str] = None


class ProposalStore(Protocol):
    def save(self, proposal: ImprovementProposal) -> None: ...
    def list_pending(self) -> List[ImprovementProposal]: ...


class FileSystemProposalStore:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.state_dir = repo_root / ".hermes" / "expansion" / "proposals"
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, proposal_id: str) -> Path:
        return self.state_dir / f"{proposal_id}.json"

    def save(self, proposal: ImprovementProposal) -> None:
        data = {
            "id": proposal.id,
            "module": proposal.module,
            "language": proposal.language,
            "description": proposal.description,
            "patch": proposal.patch,
            "risk": proposal.risk,
            "checksum_before": proposal.checksum_before,
            "checksum_after": proposal.checksum_after,
            "original_content_hex": proposal.original_content_hex,
        }
        path = self._path(proposal.id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)

    def list_pending(self) -> List[ImprovementProposal]:
        results: List[ImprovementProposal] = []
        for path in self.state_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                results.append(ImprovementProposal(**data))
            except Exception:
                continue
        return results


class SelfImprovementLoop:
    def __init__(self, config: LoopConfig) -> None:
        self.config = config
        self.state = LoopState.IDLE
        self.store = FileSystemProposalStore(config.repo_root)
        self.mutator = Mutator(config.repo_root)
        wal_path = config.repo_root / ".hermes" / "expansion" / "self_improvement.wal.jsonl"
        wal_path.parent.mkdir(parents=True, exist_ok=True)
        self.atomic_state = DurableAtomicState(wal_path)

    def start(self) -> Dict[str, Any]:
        if self.state == LoopState.RUNNING:
            return {"ok": False, "state": self.state.value}
        self.state = LoopState.RUNNING
        return {"ok": True, "state": self.state.value}

    def stop(self) -> Dict[str, Any]:
        if self.state != LoopState.RUNNING:
            return {"ok": False, "state": self.state.value}
        self.state = LoopState.IDLE
        return {"ok": True, "state": self.state.value}

    def status(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "max_workers": self.config.max_workers,
            "pending_proposals": len(self.store.list_pending()),
        }

    def propose(self, module: str, description: str, patch: str, risk: str = "low") -> ImprovementProposal:
        proposal = ImprovementProposal(
            id=f"prop-{sha256_of_bytes((module + description + patch).encode('utf-8'))[:12]}",
            module=module,
            language="python",
            description=description,
            patch=patch,
            risk=risk,
        )
        self.store.save(proposal)
        return proposal

    def apply(self, proposal_id: str) -> Dict[str, Any]:
        pending = {p.id: p for p in self.store.list_pending()}
        proposal = pending.get(proposal_id)
        if proposal is None:
            return {"ok": False, "error": "proposal not found"}

        target = self.mutator.repo_root / proposal.module
        if not target.exists():
            return {"ok": False, "error": f"module not found: {target}"}

        original = target.read_bytes()
        proposal.checksum_before = sha256_of_bytes(original)
        proposal.original_content_hex = original.hex()

        new_content = proposal.patch.encode("utf-8") if isinstance(proposal.patch, str) else proposal.patch

        validation_result = self._validate_proposal(proposal, new_content)
        if not validation_result["ok"]:
            return validation_result

        try:
            shadow = self._shadow_apply(target, new_content)
            shadow_result = self._validate_shadow(shadow)
            if not shadow_result["ok"]:
                self.atomic_state.put(f"self_improvement.apply:{proposal_id}:validation", {
                    "path": str(target),
                    "checksum_before": proposal.checksum_before,
                    "status": "validation_failed",
                    "error": shadow_result.get("error"),
                })
                return shadow_result

            self._atomic_replace(target, new_content)
            checksum_after = sha256_of_bytes(target.read_bytes())
            self.atomic_state.put(f"self_improvement.apply:{proposal_id}", {
                "path": str(target),
                "checksum_before": proposal.checksum_before,
                "checksum_after": checksum_after,
                "status": "applied",
            })
            proposal.checksum_after = checksum_after
            self.store.save(proposal)
            return {
                "ok": True,
                "path": str(target),
                "checksum_before": proposal.checksum_before,
                "checksum_after": proposal.checksum_after,
            }
        except Exception as exc:
            self.atomic_state.put(f"self_improvement.apply:{proposal_id}:error", {
                "path": str(target),
                "checksum_before": proposal.checksum_before,
                "status": "error",
                "error": str(exc),
            })
            return {"ok": False, "error": str(exc)}

    def rollback(self, proposal_id: str) -> Dict[str, Any]:
        pending = {p.id: p for p in self.store.list_pending()}
        proposal = pending.get(proposal_id)
        if proposal is None:
            return {"ok": False, "error": "proposal not found"}

        target = self.mutator.repo_root / proposal.module
        if not target.exists():
            return {"ok": False, "error": f"module not found: {target}"}

        if not proposal.original_content_hex:
            return {"ok": False, "error": "no original content recorded"}

        try:
            self._atomic_replace(target, bytes.fromhex(proposal.original_content_hex))
            self.atomic_state.put(f"self_improvement.rollback:{proposal_id}", {
                "path": str(target),
                "status": "rolled_back",
            })
            return {"ok": True, "path": str(target), "status": "rolled_back"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _validate_proposal(self, proposal: ImprovementProposal, new_content: bytes) -> Dict[str, Any]:
        try:
            if proposal.language == "python":
                compile(new_content.decode("utf-8"), proposal.module, "exec")
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": f"validation failed: {exc}"}

    def _shadow_apply(self, target: Path, new_content: bytes) -> Path:
        shadow_dir = self.config.repo_root / ".hermes" / "expansion" / "shadows"
        shadow_dir.mkdir(parents=True, exist_ok=True)
        shadow = shadow_dir / f"{target.name}.shadow-{int(time.time() * 1000)}"
        shadow.write_bytes(new_content)
        return shadow

    def _validate_shadow(self, shadow: Path) -> Dict[str, Any]:
        try:
            if not shadow.exists():
                return {"ok": False, "error": "missing shadow"}
            if shadow.suffix == ".py":
                compile(shadow.read_text(encoding="utf-8"), shadow.name, "exec")
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def _atomic_replace(target: Path, new_content: bytes) -> None:
        tmp = target.with_suffix(".tmp")
        tmp.write_bytes(new_content)
        tmp.replace(target)


def sha256_of_bytes(data: bytes) -> str:
    digest = hashlib.sha256(data)
    return digest.hexdigest()
