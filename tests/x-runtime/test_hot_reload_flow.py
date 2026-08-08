"""End-to-end supervisor-to-worker hot-reload flow."""
from __future__ import annotations

import io
import sys
import tempfile
import unittest
import threading
import time
from pathlib import Path

REPO = Path('.').resolve()
sys.path.insert(0, str(REPO / 'x-runtime' / 'python' / 'sdk' / 'src'))
sys.path.insert(0, str(REPO / 'x_bridges' / 'hermes_bridges' / 'src'))

from hermes_worker.protocol import WorkerTransport, WorkerEnvelope  # noqa: E402


def make_envelope(data: dict) -> WorkerEnvelope:
    return WorkerEnvelope(**data)


def read_envelope(buf: io.StringIO) -> dict:
    text = buf.getvalue().strip().splitlines()[-1]
    data = __import__('json').loads(text)
    return data


class TestHotReloadFlow(unittest.TestCase):
    def test_reload_request_and_completed(self) -> None:
        r = Path(tempfile.mkdtemp())
        target = r / 'module.py'
        target.write_text('v1', encoding='utf-8')

        request = make_envelope({
            'type': 'reload.request',
            'reload_id': 7,
            'path': str(target),
            'checksum': 'bad',
        })

        class FakeWorker:
            def __init__(self, transport: WorkerTransport) -> None:
                self.transport = transport
                self.handled: list[dict[str, object]] = []

            def run(self) -> None:
                self.transport.write(WorkerEnvelope(type='ready', worker_id='w1', status='healthy'))
                while True:
                    env = self.transport.read()
                    if env.type == 'reload.request':
                        self.handled.append({'reload_id': env.reload_id, 'status': 'completed'})
                        self.transport.write(WorkerEnvelope(
                            type='reload.completed',
                            reload_id=env.reload_id,
                            status='completed',
                            checksum=env.checksum or '',
                        ))
                        break
                    elif env.type == 'shutdown':
                        break

        buf = io.StringIO()
        transport = WorkerTransport(stdin=io.StringIO(request.to_json()), stdout=buf)
        worker = FakeWorker(transport)
        t = threading.Thread(target=worker.run)
        t.start()
        t.join(timeout=1)
        completed = read_envelope(buf)
        self.assertEqual(completed.get('type'), 'reload.completed')
        self.assertEqual(completed.get('reload_id'), 7)
        self.assertEqual(completed.get('status'), 'completed')


if __name__ == '__main__':
    unittest.main()
