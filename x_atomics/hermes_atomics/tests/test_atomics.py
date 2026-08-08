"""Tests for hermes_atomics.atomics."""
from __future__ import annotations

import unittest
from pathlib import Path
import tempfile

from hermes_atomics import (
    AtomicFileWrite,
    AtomicState,
    ChecksumStore,
    ReloadEvent,
)


class AtomicStateTests(unittest.TestCase):
    def test_put_get(self) -> None:
        store = AtomicState()
        store.put("lang", "python")
        self.assertEqual(store.get("lang"), "python")

    def test_compare_swap(self) -> None:
        store = AtomicState()
        store.put("mode", "agentic")
        self.assertTrue(store.compare_swap("mode", "agentic", "multi-lang"))
        self.assertEqual(store.get("mode"), "multi-lang")
        self.assertFalse(store.compare_swap("mode", "agentic", "clojure"))


class AtomicFileWriteTests(unittest.TestCase):
    def test_replace_with(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "module.py"
            target.write_text("v1", encoding="utf-8")
            writer = AtomicFileWrite(target)
            result = writer.replace_with(b"v2")
            self.assertEqual(result.read_bytes(), b"v2")


class ChecksumStoreTests(unittest.TestCase):
    def test_changed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "worker.py"
            target.write_text("alpha", encoding="utf-8")
            store = ChecksumStore()
            self.assertFalse(store.changed("worker", "stale"))
            self.assertTrue(store.changed("worker", "zzz"))


if __name__ == "__main__":
    unittest.main()
