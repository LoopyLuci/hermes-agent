"""Language-aware mutator utilities for safe code transformations."""
from __future__ import annotations

import ast
import hashlib
import difflib
from pathlib import Path
from typing import Any, Dict, Iterable, List


class Mutator:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def mutate(self, proposal: Dict[str, Any]) -> Path:
        target = self.repo_root / proposal['module']
        if not target.exists():
            raise FileNotFoundError(f"module not found: {target}")
        original = target.read_bytes()
        checksum_before = sha256_of_bytes(original)
        tmp = target.with_suffix(".tmp")
        patch = proposal['patch']
        new_content = patch.encode("utf-8") if isinstance(patch, str) else patch
        tmp.write_bytes(new_content)
        tmp.replace(target)
        proposal['checksum_before'] = checksum_before
        proposal['checksum_after'] = sha256_of_bytes(target.read_bytes())
        return target


def patch_hunk(path: Path, old: str, new: str) -> Path:
    original = path.read_text(encoding="utf-8")
    if old not in original:
        raise ValueError("old hunk not found in target")
    patched = original.replace(old, new, 1)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(patched, encoding="utf-8")
    tmp.replace(path)
    return path


def diff_lines(old_text: str, new_text: str) -> List[str]:
    return list(difflib.unified_diff(old_text.splitlines(), new_text.splitlines(), lineterm=""))


def python_symbols(source: str) -> List[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    names: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
    return names


def sha256_of_bytes(data: bytes) -> str:
    digest = hashlib.sha256(data)
    return digest.hexdigest()
