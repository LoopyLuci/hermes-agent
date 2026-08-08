"""Supervisor/worker protocol contract tests."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from urllib import request as urllib_request

REPO = Path('.').resolve()
TEMPLATE = REPO / 'x-runtime' / 'templates'
BASE = REPO / 'x-runtime'
PYTHONPATH = str(BASE / 'python' / 'sdk' / 'src')
SUPERVISOR_BIN = "hermes-runtime-supervisor.exe" if os.name == "nt" else "hermes-runtime-supervisor"
SUPERVISOR = REPO / 'x-runtime' / 'rust' / 'target' / 'debug' / SUPERVISOR_BIN
SUPERVISOR_STATUS_PORT = 18183
SUPERVISOR_HEALTH_PORT = 18185


def _wait_for(url: str, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib_request.urlopen(urllib_request.Request(url), timeout=1) as response:
                if response.status == 200:
                    return
        except Exception as exc:
            last_error = exc
            time.sleep(0.1)
    raise TimeoutError(f"url {url} not ready: {last_error}")


def _post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode('utf-8')
    req = urllib_request.Request(url, data=data, headers={'content-type': 'application/json'}, method='POST')
    with urllib_request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode('utf-8'))


class TestSupervisorWorkerProtocol(unittest.TestCase):
    def _python_worker_path(self) -> Path:
        return TEMPLATE / 'python' / 'example_worker.py'

    def _spawn_python_worker(self):
        env = os.environ.copy()
        env['PYTHONPATH'] = PYTHONPATH
        return subprocess.Popen(
            [sys.executable, str(self._python_worker_path())],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(REPO),
            env=env,
        )

    def test_python_worker_handshake_and_task(self) -> None:
        proc = self._spawn_python_worker()
        try:
            handshake = json.dumps({
                'protocol_version': '1.0',
                'message_id': 'hs-1',
                'timestamp': 0,
                'type': 'handshake',
                'worker_id': 'python-1',
                'worker_type': 'python',
                'capabilities': ['task.execute'],
                'config': {},
            }) + '\n'
            out_queue: queue.Queue[str] = queue.Queue()
            def _reader():
                for line in proc.stdout:
                    out_queue.put(line)
            threading.Thread(target=_reader, daemon=True).start()
            proc.stdin.write(handshake)
            proc.stdin.flush()
            task = json.dumps({
                'protocol_version': '1.0',
                'message_id': 't1',
                'timestamp': 0,
                'type': 'task.submit',
                'task_id': 'task-1',
                'method': 'task.echo',
                'params': {'hello': 'world'},
            }) + '\n'
            proc.stdin.write(task)
            proc.stdin.flush()
            line = out_queue.get(timeout=10)
            msg = json.loads(line)
            self.assertEqual(msg['type'], 'ready')
            line = out_queue.get(timeout=10)
            msg = json.loads(line)
            self.assertEqual(msg['type'], 'task.result')
            self.assertEqual(msg['task_id'], 'task-1')
            self.assertTrue(msg['ok'])
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass

    def test_supervisor_reload_endpoint_returns_ok(self) -> None:
        if not SUPERVISOR.exists():
            self.skipTest('supervisor binary not built')
        proc = subprocess.Popen(
            [str(SUPERVISOR), f'127.0.0.1:{SUPERVISOR_STATUS_PORT}'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            _wait_for('http://127.0.0.1:18183/status')
            worker = subprocess.Popen(
                [sys.executable, str(TEMPLATE / 'python' / 'e2e_worker.py')],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                _post('http://127.0.0.1:18183/workers', {
                    'id': 'route-test-worker',
                    'command': sys.executable,
                    'args': [str(TEMPLATE / 'python' / 'e2e_worker.py')],
                    'capabilities': ['task.execute', 'reload.request'],
                    'autostart': True,
                })
                response = _post(
                    'http://127.0.0.1:18183/workers/route-test-worker/reload',
                    {'reload_id': 1, 'checksum': 'abc'},
                )
                self.assertEqual(response.get('status'), 'reload_requested')
            finally:
                worker.terminate()
                worker.wait(timeout=5)
        finally:
            proc.terminate()
            proc.wait(timeout=5)

    def test_supervisor_status_endpoint_returns_json(self) -> None:
        if not SUPERVISOR.exists():
            self.skipTest('supervisor binary not built')
        proc = subprocess.Popen(
            [str(SUPERVISOR), '127.0.0.1:18184'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            _wait_for('http://127.0.0.1:18184/status')
            with urllib_request.urlopen(urllib_request.Request('http://127.0.0.1:18184/status'), timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
            self.assertIn('supervisor_id', data)
            self.assertIn('worker_count', data)
            self.assertIn('workers', data)
        finally:
            proc.terminate()
            proc.wait(timeout=5)

    def test_supervisor_health_endpoint_returns_json(self) -> None:
        if not SUPERVISOR.exists():
            self.skipTest('supervisor binary not built')
        proc = subprocess.Popen(
            [str(SUPERVISOR), f'127.0.0.1:{SUPERVISOR_HEALTH_PORT}'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            _wait_for('http://127.0.0.1:18185/status')
            try:
                with urllib_request.urlopen(urllib_request.Request('http://127.0.0.1:18185/healthz'), timeout=5) as response:
                    data = json.loads(response.read().decode('utf-8'))
            except urllib_request.HTTPError as exc:
                data = json.loads(exc.read().decode('utf-8'))
            self.assertIn('status', data)
        finally:
            proc.terminate()
            proc.wait(timeout=5)

    def test_auto_restart_module_exists(self) -> None:
        restart_file = BASE / 'rust' / 'supervisor' / 'src' / 'auto_restart.rs'
        self.assertTrue(restart_file.exists())

    def test_protocol_version_field_present(self) -> None:
        protocol = BASE / 'protocol' / 'v1' / 'protocol.md'
        self.assertTrue(protocol.exists())
        text = protocol.read_text(encoding='utf-8')
        self.assertIn('protocol_version', text)
        self.assertIn('v2', text)

    def test_worker_templates_exist(self) -> None:
        expected = [
            TEMPLATE / 'python' / 'example_worker.py',
            TEMPLATE / 'clojure' / 'example_worker.clj',
            TEMPLATE / 'typescript' / 'example_worker.ts',
            TEMPLATE / 'rust' / 'src' / 'main.rs',
        ]
        for path in expected:
            self.assertTrue(path.exists(), msg=f'missing template: {path}')


if __name__ == '__main__':
    unittest.main()
