"""Crash-injection style tests for durable atomics."""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path('.').resolve()


class TestDurableAtomicCrash(unittest.TestCase):
    def test_partial_wal_line_does_not_corrupt_state(self) -> None:
        wal = pathlib.Path(tempfile.gettempdir()) / 'hermes-crash-tests-wal.jsonl'
        if wal.exists():
            wal.unlink()
        wal.write_text('{"key":"x","next":1}\n{"key":"y","next":2\n{"key":"z","next":3}\n', encoding='utf-8')
        script = REPO / 'x_bridges' / 'hermes_bridges' / 'src' / 'hermes_bridges' / 'bridge' / 'durable_atomic.py'
        proc = subprocess.run(
            [sys.executable, '-c', f'''
import sys
sys.path.insert(0, r"{REPO / 'x_bridges' / 'hermes_bridges' / 'src'}")
from hermes_bridges.bridge.durable_atomic import DurableAtomicState
state = DurableAtomicState(r"{wal}")
print(state.get("z"))
print(state.get("y"))
print(state.get("x"))
'''],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertEqual(proc.stdout.strip().splitlines(), ['3', 'None', '1'])

    def test_wal_replay_after_simulated_crash(self) -> None:
        wal = pathlib.Path(tempfile.gettempdir()) / 'hermes-replay-wal.jsonl'
        if wal.exists():
            wal.unlink()
        wal.write_text(
            '\n'.join([
                json.dumps({"key": "mode", "prev": None, "next": "agentic", "checksum": "abc", "timestamp": 1}),
                json.dumps({"key": "mode", "prev": "agentic", "next": "autonomous", "checksum": "def", "timestamp": 2}),
            ]) + '\n',
            encoding='utf-8',
        )
        script = REPO / 'x_bridges' / 'hermes_bridges' / 'src' / 'hermes_bridges' / 'bridge' / 'durable_atomic.py'
        proc = subprocess.run(
            [sys.executable, '-c', f'''
import sys
sys.path.insert(0, r"{REPO / 'x_bridges' / 'hermes_bridges' / 'src'}")
from hermes_bridges.bridge.durable_atomic import DurableAtomicState
state = DurableAtomicState(r"{wal}")
print(state.get("mode"))
'''],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertEqual(proc.stdout.strip(), 'autonomous')


if __name__ == '__main__':
    unittest.main()
