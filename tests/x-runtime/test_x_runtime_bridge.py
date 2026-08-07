from __future__ import annotations

import time
import unittest
from pathlib import Path
from unittest import mock

from hermes_cli.x_runtime_bridge import (
    XRuntimeBridge,
    XRuntimeBridgeAbiMismatch,
    XRuntimeBridgeDisabled,
    XRuntimeBridgeUnavailable,
    _missing_abi_reason,
    check_abi_version,
    load_abi_library,
)


class TestBridgeDisabledAndUnavailable(unittest.TestCase):
    def test_disabled_raises(self) -> None:
        bridge = XRuntimeBridge(enabled=False, endpoint="http://127.0.0.1:18181")
        with self.assertRaises(XRuntimeBridgeDisabled):
            bridge.maybe_dispatch({}, {})

    def test_missing_endpoint_raises(self) -> None:
        bridge = XRuntimeBridge(enabled=True, endpoint=None)
        with self.assertRaises(XRuntimeBridgeUnavailable):
            bridge.maybe_dispatch({}, {})

    def test_missing_abi_raises(self) -> None:
        with mock.patch(
            "hermes_cli.x_runtime_bridge.load_abi_library", return_value=None
        ):
            bridge = XRuntimeBridge(
                enabled=True, endpoint="http://127.0.0.1:18181"
            )
            with self.assertRaises(XRuntimeBridgeUnavailable):
                bridge.maybe_dispatch({}, {})

    def test_abi_version_mismatch_raises(self) -> None:
        abi = Path("x-runtime/rust/target/release/hermes_runtime_abi.dll")
        if not abi.exists():
            self.skipTest("abi dll missing")
        with mock.patch(
            "hermes_cli.x_runtime_bridge.load_abi_library", return_value=abi
        ), mock.patch(
            "hermes_cli.x_runtime_bridge.check_abi_version", return_value=2
        ):
            bridge = XRuntimeBridge(
                enabled=True, endpoint="http://127.0.0.1:18181"
            )
            with self.assertRaises(XRuntimeBridgeAbiMismatch):
                bridge.maybe_dispatch({}, {})


class TestCircuitBreaker(unittest.TestCase):
    def test_opens_after_threshold(self) -> None:
        bridge = XRuntimeBridge(
            enabled=True,
            endpoint="http://127.0.0.1:18181",
            circuit_breaker=_FakeBreaker(threshold=2),
        )
        with mock.patch(
            "hermes_cli.x_runtime_bridge.load_abi_library", return_value=Path("x")
        ), mock.patch(
            "hermes_cli.x_runtime_bridge.check_abi_version", return_value=1
        ), mock.patch(
            "urllib.request.urlopen", side_effect=OSError("boom")
        ):
            for _ in range(2):
                with self.assertRaises(XRuntimeBridgeUnavailable):
                    bridge.maybe_dispatch({}, {})
            with self.assertRaises(XRuntimeBridgeUnavailable):
                bridge.maybe_dispatch({}, {})

    def test_recovers_after_timeout(self) -> None:
        breaker = _FakeBreaker(threshold=1, recovery_timeout=0.01)
        bridge = XRuntimeBridge(
            enabled=True,
            endpoint="http://127.0.0.1:18181",
            circuit_breaker=breaker,
        )
        ctx = mock.MagicMock()
        ctx.__enter__ = mock.Mock(return_value=ctx)
        ctx.__exit__ = mock.Mock(return_value=False)
        ctx.read.return_value = b'"ok"'
        ctx.status = 200
        with mock.patch(
            "hermes_cli.x_runtime_bridge.load_abi_library", return_value=Path("x")
        ), mock.patch(
            "hermes_cli.x_runtime_bridge.check_abi_version", return_value=1
        ), mock.patch(
            "urllib.request.urlopen", side_effect=[OSError("boom"), ctx]
        ):
            with self.assertRaises(XRuntimeBridgeUnavailable):
                bridge.maybe_dispatch({}, {})
            time.sleep(0.02)
            result = bridge.maybe_dispatch({}, {})
            self.assertIsNotNone(result)


class _FakeBreaker:
    def __init__(self, threshold: int = 3, recovery_timeout: float = 30.0) -> None:
        self.failure_threshold = threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = 1
        self._failure_count = 0
        self._state = "closed"
        self._last_failure_time = None
        self._half_open_calls = 0

    def allow_request(self) -> bool:
        if self._state == "closed":
            return True
        if self._state == "open":
            if self._last_failure_time is None:
                return False
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._state = "half_open"
                self._half_open_calls = 0
                return True
            return False
        if self._state == "half_open":
            if self._half_open_calls < self.half_open_max_calls:
                return True
            return False
        return False

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._state == "half_open" or self._failure_count >= self.failure_threshold:
            self._state = "open"
            self._half_open_calls = 0

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = "closed"
        self._half_open_calls = 0
        self._last_failure_time = None


if __name__ == "__main__":
    unittest.main()
