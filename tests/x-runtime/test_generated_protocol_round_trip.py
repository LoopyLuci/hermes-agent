"""Generated protocol round-trip tests for Python."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path('.').resolve()
sys.path.insert(0, str(REPO / 'x-runtime' / 'python' / 'sdk' / 'src'))


class TestGeneratedProtocolRoundTrip(unittest.TestCase):
    def test_generated_module_imports(self) -> None:
        from hermes_worker.generated_protocol import (  # noqa: F401
            Handshake,
            Ready,
            ReloadCompleted,
            ReloadRequest,
            Shutdown,
            TaskResult,
            TaskSubmit,
        )

    def test_handshake_round_trip(self) -> None:
        from hermes_worker.generated_protocol import Handshake

        payload = Handshake(
            protocol_version='1.0',
            message_id='hs-1',
            timestamp=0,
            kind='handshake',
            worker_id='python-1',
            worker_type='python',
            capabilities=['task.execute'],
            config={},
        )
        self.assertEqual(payload.kind, 'handshake')
        self.assertEqual(payload.worker_id, 'python-1')
        self.assertEqual(payload.protocol_version, '1.0')
        self.assertEqual(payload.timestamp, 0)

    def test_task_submit_round_trip(self) -> None:
        from hermes_worker.generated_protocol import TaskSubmit

        payload = TaskSubmit(
            protocol_version='1.0',
            message_id='t1',
            timestamp=0,
            kind='task.submit',
            task_id='task-1',
            method='task.echo',
            params={'hello': 'world'},
            timeout_ms=5000,
        )
        self.assertEqual(payload.kind, 'task.submit')
        self.assertEqual(payload.method, 'task.echo')
        self.assertEqual(payload.task_id, 'task-1')


if __name__ == '__main__':
    unittest.main()
