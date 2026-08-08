"""Hermes core integration tests for optional x-runtime bridge."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent


def _write_temp_hermes_home(tmp_root: Path) -> Path:
    hermes_home = tmp_root / "home" / ".hermes"
    hermes_home.mkdir(parents=True)
    config = hermes_home / "config.yaml"
    config.write_text(
        "model:\n  provider: test\n  model: test-model\n",
        encoding="utf-8",
    )
    return hermes_home


class TestXRuntimeHermesIntegration(unittest.TestCase):
    def test_default_config_does_not_enable_x_runtime(self) -> None:
        from hermes_cli.config import DEFAULT_CONFIG

        x_runtime = ((DEFAULT_CONFIG or {}).get("x_runtime") or {})
        self.assertFalse(bool(x_runtime.get("enabled")))

    def test_temp_hermes_home_bridge_disabled_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hermes_home = _write_temp_hermes_home(Path(tmp))
            old_home = os.environ.get("HERMES_HOME")
            old_cwd = os.getcwd()
            try:
                os.environ["HERMES_HOME"] = str(hermes_home)
                os.chdir(str(REPO))
                from hermes_cli.x_runtime_bridge import resolve_x_runtime_runtime_credentials

                with self.assertRaises(Exception) as ctx:
                    resolve_x_runtime_runtime_credentials({})
                self.assertIn("not enabled", str(ctx.exception))
            finally:
                if old_home is None:
                    os.environ.pop("HERMES_HOME", None)
                else:
                    os.environ["HERMES_HOME"] = old_home
                os.chdir(old_cwd)

    def test_enabled_bridge_returns_credentials_from_temp_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hermes_home = _write_temp_hermes_home(Path(tmp))
            old_home = os.environ.get("HERMES_HOME")
            old_cwd = os.getcwd()
            try:
                os.environ["HERMES_HOME"] = str(hermes_home)
                os.chdir(str(REPO))
                from hermes_cli.x_runtime_bridge import resolve_x_runtime_runtime_credentials

                with mock.patch(
                    "hermes_cli.x_runtime_bridge._missing_abi_reason", return_value=None
                ):
                    result = resolve_x_runtime_runtime_credentials({
                        "x_runtime": {
                            "enabled": True,
                            "endpoint": "http://127.0.0.1:18181",
                            "worker_capabilities": ["task.execute"],
                        }
                    })
                self.assertEqual(result["runtime"], "x-runtime")
                self.assertEqual(result["endpoint"], "http://127.0.0.1:18181")
            finally:
                if old_home is None:
                    os.environ.pop("HERMES_HOME", None)
                else:
                    os.environ["HERMES_HOME"] = old_home
                os.chdir(old_cwd)

    def test_model_tools_default_path_untouched_when_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _write_temp_hermes_home(Path(tmp))
            old_home = os.environ.get("HERMES_HOME")
            old_cwd = os.getcwd()
            try:
                os.environ["HERMES_HOME"] = str(tmp)
                os.chdir(str(REPO))
                import model_tools

                with mock.patch("hermes_cli.config.load_config", return_value={}):
                    result = model_tools._maybe_dispatch_x_runtime(
                        "terminal",
                        {"command": "pwd"},
                        task_id="t1",
                        session_id="s1",
                    )
                self.assertIsNone(result)
            finally:
                if old_home is None:
                    os.environ.pop("HERMES_HOME", None)
                else:
                    os.environ["HERMES_HOME"] = old_home
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
