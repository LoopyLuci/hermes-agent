"""Verification for self-improvement durable atomic wiring."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path('.').resolve()
sys.path.insert(0, str(REPO / 'x-runtime' / 'python' / 'sdk' / 'src'))
sys.path.insert(0, str(REPO / 'x_bridges' / 'hermes_bridges' / 'src'))


class TestSelfImprovementDurable(unittest.TestCase):
    def test_imports(self) -> None:
        from hermes_bridges.self_improvement.loop import LoopConfig, SelfImprovementLoop  # noqa: F401
        from hermes_bridges.bridge.durable_atomic import DurableAtomicState  # noqa: F401

    def test_apply_records_wal_and_checksums(self) -> None:
        from hermes_bridges.self_improvement.loop import LoopConfig, SelfImprovementLoop

        with tempfile.TemporaryDirectory() as td:
            r = Path(td)
            cfg = LoopConfig(repo_root=r, watch_paths=[], max_workers=1)
            loop = SelfImprovementLoop(cfg)
            target = r / 'module.py'
            target.write_text('original', encoding='utf-8')
            proposal = loop.propose('module.py', 'update', 'updated', risk='low')
            result = loop.apply(proposal.id)
            self.assertTrue(result['ok'], result)
            self.assertEqual(target.read_text(encoding='utf-8'), 'updated')
            self.assertNotEqual(result['checksum_before'], result['checksum_after'])
            wal = r / '.hermes' / 'expansion' / 'self_improvement.wal.jsonl'
            self.assertTrue(wal.exists())
            lines = wal.read_text(encoding='utf-8').splitlines()
            self.assertTrue(any('self_improvement.apply:' in line for line in lines))


if __name__ == '__main__':
    unittest.main()
