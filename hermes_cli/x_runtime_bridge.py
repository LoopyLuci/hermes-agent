from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class XRuntimeBridgeDisabled(Exception):
    """Raised when x-runtime is disabled by config."""


class XRuntimeBridgeAbiMismatch(Exception):
    """Raised when the ABI major version does not match."""


class XRuntimeBridgeUnavailable(Exception):
    """Raised when the supervisor endpoint cannot be reached."""


@dataclass
class BridgeCircuitBreaker:
    failure_threshold: int = 3
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 1
    _failure_count: int = 0
    _state: str = "closed"
    _last_failure_time: Optional[float] = None
    _half_open_calls: int = 0

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


_default_circuit_breaker = BridgeCircuitBreaker()


def _default_abi_path() -> Optional[Path]:
    return Path("x-runtime/rust/target/release/hermes_runtime_abi.dll")


def load_abi_library(abi_path: Optional[Path] = None) -> Optional[Path]:
    candidate = abi_path or _default_abi_path()
    if candidate and candidate.exists():
        return candidate
    return None


def check_abi_version(abi_path: Path) -> int:
    try:
        import ctypes

        lib = ctypes.CDLL(str(abi_path))
        lib.stable_abi_manifest_size.restype = ctypes.c_ulong
        size = lib.stable_abi_manifest_size()
        buf = ctypes.create_string_buffer(size)
        lib.stable_abi_manifest_default.argtypes = [ctypes.c_void_p]
        lib.stable_abi_manifest_default(buf)
        major = int.from_bytes(buf.raw[0:8], "little")
        return major
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("abi version check failed: %s", exc)
        return -1


def _missing_abi_reason(abi_path: Optional[Path] = None) -> Optional[str]:
    candidate = abi_path or _default_abi_path()
    if candidate is None or not candidate.exists():
        return "missing ABI library"
    if check_abi_version(candidate) != 1:
        return "ABI major version mismatch"
    return None


class XRuntimeBridge:
    def __init__(
        self,
        enabled: bool = False,
        endpoint: Optional[str] = None,
        abi_path: Optional[Path] = None,
        request_timeout: float = 2.0,
        circuit_breaker: Optional[BridgeCircuitBreaker] = None,
    ) -> None:
        self.enabled = enabled
        self.endpoint = endpoint
        self.abi_path = abi_path
        self.request_timeout = request_timeout
        self.circuit_breaker = circuit_breaker or _default_circuit_breaker

    def _resolve_endpoint(self, config: dict) -> Optional[str]:
        return self.endpoint or config.get("endpoint")

    def maybe_dispatch(self, payload: dict, config: Optional[dict] = None) -> Optional[str]:
        if not self.enabled:
            raise XRuntimeBridgeDisabled("x-runtime is disabled")

        endpoint = self._resolve_endpoint(config or {})
        if not endpoint:
            raise XRuntimeBridgeUnavailable("x-runtime endpoint is not configured")

        if not self.circuit_breaker.allow_request():
            raise XRuntimeBridgeUnavailable("x-runtime circuit breaker is open")

        abi = load_abi_library(self.abi_path)
        if abi is None:
            raise XRuntimeBridgeUnavailable("x-runtime ABI library is missing")

        if check_abi_version(abi) != 1:
            raise XRuntimeBridgeAbiMismatch("x-runtime ABI major version mismatch")

        try:
            import urllib.request

            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                body = resp.read().decode("utf-8")
            self.circuit_breaker.record_success()
            return body
        except Exception as exc:
            self.circuit_breaker.record_failure()
            logger.debug("x-runtime dispatch failed: %s", exc)
            raise XRuntimeBridgeUnavailable(f"x-runtime dispatch failed: {exc}") from exc


_default_bridge = XRuntimeBridge()


def resolve_x_runtime_runtime_credentials(
    config: dict,
    *,
    abi_path: Optional[Path] = None,
) -> dict:
    x_runtime = config.get("x_runtime") or {}
    if not x_runtime.get("enabled"):
        raise XRuntimeBridgeDisabled("x-runtime is not enabled")

    missing = _missing_abi_reason(abi_path)
    if missing:
        raise XRuntimeBridgeUnavailable(f"x-runtime ABI unavailable: {missing}")

    endpoint = x_runtime.get("endpoint")
    if not endpoint:
        raise XRuntimeBridgeUnavailable("x-runtime endpoint is not configured")

    return {
        "runtime": "x-runtime",
        "endpoint": endpoint,
        "worker_capabilities": x_runtime.get("worker_capabilities", []),
    }


def _maybe_dispatch_x_runtime(
    toolset: str,
    payload: dict,
    config: Optional[dict] = None,
    *,
    task_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Optional[str]:
    try:
        enriched = dict(payload or {})
        enriched.setdefault("toolset", toolset)
        if task_id:
            enriched.setdefault("task_id", task_id)
        if session_id:
            enriched.setdefault("session_id", session_id)
        return _default_bridge.maybe_dispatch(enriched, config)
    except (XRuntimeBridgeDisabled, XRuntimeBridgeUnavailable, XRuntimeBridgeAbiMismatch) as exc:
        logger.debug("x-runtime dispatch skipped: %s", exc)
        return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("x-runtime dispatch errored: %s", exc)
        return None
