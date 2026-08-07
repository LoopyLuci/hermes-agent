"""Full cross-language workflow: dispatch -> reload -> dispatch."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock
from urllib import request as urllib_request

REPO = Path(__file__).resolve().parent.parent.parent
SUPERVISOR = REPO / "x-runtime" / "rust" / "target" / "debug" / "hermes-runtime-supervisor.exe"
E2E_WORKER = REPO / "x-runtime" / "templates" / "python" / "e2e_worker.py"


def _write_temp_hermes_home(tmp_root: Path) -> Path:
    hermes_home = tmp_root / "home" / ".hermes"
    hermes_home.mkdir(parents=True)
    (hermes_home / "config.yaml").write_text(
        "model:\n"
        "  provider: test\n"
        "  model: test-model\n"
        "x_runtime:\n"
        "  enabled: true\n"
        "  endpoint: http://127.0.0.1:18181\n",
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


class TestCrossLanguageWorkflowLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        if not SUPERVISOR.exists() or not E2E_WORKER.exists():
            self.skipTest("supervisor or e2e worker missing")

    def test_full_lifecycle_dispatch_reload_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hermes_home = _write_temp_hermes_home(Path(tmp))
            old_home = os.environ.get("HERMES_HOME")
            old_cwd = os.getcwd()
            try:
                os.environ["HERMES_HOME"] = str(hermes_home)
                os.chdir(str(REPO))

                proc = subprocess.Popen(
                    [str(SUPERVISOR), "127.0.0.1:18181"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                try:
                    _wait_for("http://127.0.0.1:18181/status")
                    worker = subprocess.Popen(
                        [sys.executable, str(E2E_WORKER)],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    try:
                        _post(
                            "http://127.0.0.1:18181/workers",
                            {
                                "id": "lifecycle-worker",
                                "command": sys.executable,
                                "args": [str(E2E_WORKER)],
                                "capabilities": ["task.execute", "reload.request"],
                                "autostart": True,
                            },
                        )

                        import model_tools

                        with mock.patch("hermes_cli.config.load_config", return_value={
                            "x_runtime": {"enabled": True, "endpoint": "http://127.0.0.1:18181"}
                        }), mock.patch("hermes_cli.x_runtime_bridge._missing_abi_reason", return_value=None):
                            first = model_tools._maybe_dispatch_x_runtime(
                                "terminal",
                                {"command": "pwd"},
                                task_id="lifecycle-1",
                                session_id="lifecycle-session",
                            )
                        self.assertIsNotNone(first)
                        self.assertIn('"ok"', first)

                        reload_response = _post(
                            "http://127.0.0.1:18181/workers/lifecycle-worker/reload",
                            {"reload_id": 1, "checksum": "abc", "path": str(E2E_WORKER)},
                        )
                        self.assertEqual(reload_response.get("status"), "reload_requested")

                        deadline = time.time() + 5
                        while time.time() < deadline:
                            with mock.patch("hermes_cli.config.load_config", return_value={
                                "x_runtime": {"enabled": True, "endpoint": "http://127.0.0.1:18181"}
                            }), mock.patch("hermes_cli.x_runtime_bridge._missing_abi_reason", return_value=None):
                                after = model_tools._maybe_dispatch_x_runtime(
                                    "terminal",
                                    {"command": "pwd"},
                                    task_id="lifecycle-2",
                                    session_id="lifecycle-session",
                                )
                            if after is not None and '"ok"' in after:
                                break
                            time.sleep(0.1)
                        self.assertIsNotNone(after)
                        self.assertIn('"ok"', after)
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
