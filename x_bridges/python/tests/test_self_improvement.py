"""Tests for hermes_bridges.self_improvement."""
from __future__ import annotations

import unittest
from pathlib import Path
import tempfile

from hermes_bridges.self_improvement.loop import LoopConfig, SelfImprovementLoop
from hermes_bridges.self_improvement.mutator import python_symbols


class SelfImprovementLoopTests(unittest.TestCase):
    def test_start_stop(self) -> None:
        config = LoopConfig(repo_root=Path(".").resolve())
        loop = SelfImprovementLoop(config)
        self.assertEqual(loop.status()["state"], "idle")
        self.assertTrue(loop.start()["ok"])
        self.assertEqual(loop.status()["state"], "running")
        self.assertTrue(loop.stop()["ok"])
        self.assertEqual(loop.status()["state"], "idle")

    def test_propose_and_list(self) -> None:
        config = LoopConfig(repo_root=Path(".").resolve())
        loop = SelfImprovementLoop(config)
        proposal = loop.propose("agent/agent_init.py", "Add comment", "# comment\n")
        self.assertIsNotNone(proposal.id)
        self.assertEqual(len(loop.store.list_pending()), 1)


class MutatorTests(unittest.TestCase):
    def test_python_symbols(self) -> None:
        source = "def foo(): pass\nclass Bar: pass\n"
        names = python_symbols(source)
        self.assertEqual(names, ["foo", "Bar"])


if __name__ == "__main__":
    unittest.main()
