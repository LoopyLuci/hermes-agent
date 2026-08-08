"""Concurrent reload atomicity tests for the x-runtime supervisor."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib import request as urllib_request

REPO = Path(__file__).resolve().parent.parent.parent
SUPERVISOR_BIN = "hermes-runtime-supervisor.exe" if os.name == "nt" else "hermes-runtime-supervisor"
SUPERVISOR = REPO / "x-runtime" / "rust" / "target" / "debug" / SUPERVISOR_BIN
CONCURRENT_WORKER = REPO / "x-runtime" / "templates" / "python" / "concurrent_worker.py"


def _write_temp_hermes_home(tmp_root: Path) -> Path:
    hermes_home = tmp_root / "home" / ".hermes"
    hermes_home.mkdir(parents=True)
    (hermes_home / "config.yaml").write_text(
        "model:\n"
        "  provider: test\n"
        "  model: test-model\n"
        "x_runtime:\n"
        "  enabled: true\n"
        "  endpoint: http://127.0.0.1:18182\n",
        encoding="utf-8",
    )
    return hermes_home


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


def _post(url: str, payload: dict[str, object]) -> dict[str, object]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(url, data=data, headers={"content-type": "application/json"}, method="POST")
    with urllib_request.urlopen(req, timeout=5) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw)


class TestConcurrentReloadAtomicity(unittest.TestCase):
    def setUp(self) -> None:
        if not SUPERVISOR.exists():
            self.skipTest("supervisor binary not built")

    def test_overlapping_reload_and_task_calls_retain_all_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hermes_home = _write_temp_hermes_home(Path(tmp))
            old_home = os.environ.get("HERMES_HOME")
            old_cwd = os.getcwd()
            try:
                os.environ["HERMES_HOME"] = str(hermes_home)
                os.chdir(str(REPO))

                proc = subprocess.Popen(
                    [str(SUPERVISOR), "127.0.0.1:18182"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                try:
                    _wait_for("http://127.0.0.1:18182/status")
                    worker = subprocess.Popen(
                        [sys.executable, str(CONCURRENT_WORKER)],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    try:
                        _post("http://127.0.0.1:18182/workers", {
                            "id": "concurrent-worker",
                            "command": sys.executable,
                            "args": [str(CONCURRENT_WORKER)],
                            "capabilities": ["task.execute", "reload.request"],
                            "autostart": True,
                        })

                        results = []

                        def _dispatch(task_id: str, session_id: str):
                            import model_tools
                            from unittest import mock
                            with mock.patch("hermes_cli.config.load_config", return_value={
                                "x_runtime": {"enabled": True, "endpoint": "http://127.0.0.1:18182"}
                            }):
                                result = model_tools._maybe_dispatch_x_runtime(
                                    "terminal",
                                    {"command": "pwd", "value": "pwd"},
                                    task_id=task_id,
                                    session_id=session_id,
                                )
                            results.append(result)

                        threads = [
                            threading.Thread(target=_dispatch, args=("c1", "s1")),
                            threading.Thread(target=_dispatch, args=("c2", "s1")),
                        ]
                        for thread in threads:
                            thread.start()
                        _post("http://127.0.0.1:18182/workers/concurrent-worker/reload", {"reload_id": 1, "checksum": "abc", "path": str(CONCURRENT_WORKER)})
                        threads.append(threading.Thread(target=_dispatch, args=("c3", "s1")))
                        threads[-1].start()
                        for thread in threads:
                            thread.join(timeout=30)

                        self.assertEqual(len(results), 3)
                        for result in results:
                            self.assertIsNotNone(result)
                            self.assertIn('"ok"', result)
                    finally:
                        worker.terminate()
                        worker.wait(timeout=5)
                finally:
                    proc.terminate()
                    proc.wait(timeout=5)
            finally:
                if old_home is None:
                    os.environ.pop("HERMES_HOME", None)
                else:
                    os.environ["HERMES_HOME"] = old_home
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
