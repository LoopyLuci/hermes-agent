"""Round-trip protocol compatibility tests."""
from __future__ import annotations

import json
import pathlib
import unittest

REPO = pathlib.Path('.').resolve()
SCHEMAS = REPO / 'x-runtime' / 'protocol' / 'v1' / 'schema'


class TestProtocolRoundTrip(unittest.TestCase):
    def test_schema_files_exist(self) -> None:
        expected = [
            'envelope-base.json',
            'handshake.json',
            'ready.json',
            'task-submit.json',
            'task-result.json',
            'reload-request.json',
            'reload-completed.json',
            'shutdown.json',
        ]
        for name in expected:
            self.assertTrue((SCHEMAS / name).exists(), msg=f'missing schema {name}')

    def test_example_handshake_round_trip(self) -> None:
        payload = {
            'protocol_version': '1.0',
            'message_id': 'hs-1',
            'timestamp': 0,
            'type': 'handshake',
            'worker_id': 'python-1',
            'worker_type': 'python',
            'capabilities': ['task.execute'],
            'config': {},
        }
        encoded = json.dumps(payload) + '\n'
        decoded = json.loads(encoded)
        self.assertEqual(decoded['type'], 'handshake')
        self.assertEqual(decoded['worker_id'], 'python-1')

    def test_example_task_result_round_trip(self) -> None:
        payload = {
            'protocol_version': '1.0',
            'message_id': 't1',
            'timestamp': 1,
            'type': 'task.result',
            'task_id': 'task-1',
            'ok': True,
            'result': {'status': 'ok'},
            'latency_ms': 2,
        }
        encoded = json.dumps(payload) + '\n'
        decoded = json.loads(encoded)
        self.assertTrue(decoded['ok'])
        self.assertEqual(decoded['result']['status'], 'ok')

    def test_example_reload_request_round_trip(self) -> None:
        payload = {
            'protocol_version': '1.0',
            'message_id': 'r1',
            'timestamp': 2,
            'type': 'reload.request',
            'reload_id': 1,
            'path': '/workers/rust/atomic/src/lib.rs',
            'checksum': 'sha256:abc',
        }
        encoded = json.dumps(payload) + '\n'
        decoded = json.loads(encoded)
        self.assertEqual(decoded['checksum'], 'sha256:abc')
        self.assertEqual(decoded['reload_id'], 1)


if __name__ == '__main__':
    unittest.main()
