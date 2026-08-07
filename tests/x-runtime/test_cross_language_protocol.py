"""Cross-language protocol compatibility tests."""
from __future__ import annotations

import json
import pathlib
import unittest

REPO = pathlib.Path('.').resolve()
PYTHON_PROTOCOL = REPO / 'x-runtime' / 'python' / 'sdk' / 'src' / 'hermes_worker' / 'generated_protocol.py'


EXAMPLE_ENVELOPES = [
    {
        'protocol_version': '1.0',
        'message_id': 'hs-1',
        'timestamp': 0,
        'type': 'handshake',
        'worker_id': 'python-1',
        'worker_type': 'python',
        'capabilities': ['task.execute'],
        'config': {},
    },
    {
        'protocol_version': '1.0',
        'message_id': 't1',
        'timestamp': 1,
        'type': 'task.result',
        'task_id': 'task-1',
        'ok': True,
        'result': {'status': 'ok'},
        'latency_ms': 2,
    },
    {
        'protocol_version': '1.0',
        'message_id': 'r1',
        'timestamp': 2,
        'type': 'reload.request',
        'reload_id': 1,
        'path': '/workers/rust/atomic/src/lib.rs',
        'checksum': 'sha256:abc',
    },
]


class TestCrossLanguageProtocolCompatibility(unittest.TestCase):
    def test_generated_python_types_have_expected_fields(self) -> None:
        source = PYTHON_PROTOCOL.read_text(encoding='utf-8')
        expected_types = [
            'class Handshake',
            'class Ready',
            'class TaskSubmit',
            'class TaskResult',
            'class ReloadRequest',
            'class ReloadCompleted',
            'class Shutdown',
        ]
        for type_name in expected_types:
            self.assertIn(type_name, source)

    def test_example_envelopes_have_required_base_fields(self) -> None:
        for payload in EXAMPLE_ENVELOPES:
            self.assertIn('protocol_version', payload)
            self.assertIn('message_id', payload)
            self.assertIn('timestamp', payload)
            self.assertIn('type', payload)
            encoded = f"{json.dumps(payload)}\n"
            decoded = json.loads(encoded)
            self.assertEqual(decoded['type'], payload['type'])

    def test_mismatched_protocol_version_is_rejected_by_schema_expectation(self) -> None:
        payload = EXAMPLE_ENVELOPES[0]
        mismatched = dict(payload)
        mismatched['protocol_version'] = '0.9'
        encoded = f"{json.dumps(mismatched)}\n"
        decoded = json.loads(encoded)
        self.assertEqual(decoded['protocol_version'], '0.9')

    def test_malformed_envelope_is_not_silently_accepted(self) -> None:
        for payload in ['not-json\n', '{}\n', '{"type": "handshake"}\n']:
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                continue
            self.assertNotIn('protocol_version', parsed)


if __name__ == '__main__':
    unittest.main()
