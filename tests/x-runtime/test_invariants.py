"""Invariant tests for hot-reload and self-improvement."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path('.').resolve()
sys.path.insert(0, str(REPO / 'x-runtime' / 'python' / 'sdk' / 'src'))
sys.path.insert(0, str(REPO / 'x_bridges' / 'hermes_bridges' / 'src'))

from hermes_bridges.self_improvement.loop import SelfImprovementLoop, LoopConfig
from hermes_worker.protocol import WorkerTransport, WorkerEnvelope


class TestHotReloadInvariants(unittest.TestCase):
    def test_malformed_envelope_exits_cleanly(self) -> None:
        buf = sys.stdout
        fake_stdin = io.StringIO('not-json\n')
        transport = WorkerTransport(stdin=fake_stdin, stdout=buf)

        class FakeWorker:
            def run(self) -> None:
                transport.write(WorkerEnvelope(type='ready', worker_id='w1', status='healthy'))
                transport.read()

        with self.assertRaises(json.JSONDecodeError):
            FakeWorker().run()


class TestSelfImprovementInvariants(unittest.TestCase):
    def test_invalid_patch_is_rejected_and_original_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            target = repo / 'module.py'
            original = 'x = 1\n'
            target.write_text(original, encoding='utf-8')

            loop = SelfImprovementLoop(LoopConfig(repo_root=repo))
            result = loop.apply('does-not-matter')

            self.assertFalse(result['ok'])
            self.assertEqual(target.read_text(encoding='utf-8'), original)


if __name__ == '__main__':
    unittest.main()
