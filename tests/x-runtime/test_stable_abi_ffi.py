"""Stable ABI/FFI binding tests using ctypes against the Rust cdylib."""
from __future__ import annotations

import ctypes
import os
import unittest


class TestStableAbiFfi(unittest.TestCase):
    @classmethod
    def _load_library(cls):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
        if os.name == "nt":
            candidates = [
                os.path.join(repo_root, "x-runtime", "rust", "target", "release", "hermes_runtime_abi.dll"),
                os.path.join(repo_root, "x-runtime", "rust", "target", "release", "libhermes_runtime_abi.so"),
                os.path.join(repo_root, "x-runtime", "rust", "target", "release", "libhermes_runtime_abi.dylib"),
            ]
        elif os.name == "darwin":
            candidates = [
                os.path.join(repo_root, "x-runtime", "rust", "target", "release", "libhermes_runtime_abi.dylib"),
                os.path.join(repo_root, "x-runtime", "rust", "target", "release", "libhermes_runtime_abi.so"),
                os.path.join(repo_root, "x-runtime", "rust", "target", "release", "hermes_runtime_abi.dll"),
            ]
        else:
            candidates = [
                os.path.join(repo_root, "x-runtime", "rust", "target", "release", "libhermes_runtime_abi.so"),
                os.path.join(repo_root, "x-runtime", "rust", "target", "release", "hermes_runtime_abi.dll"),
                os.path.join(repo_root, "x-runtime", "rust", "target", "release", "libhermes_runtime_abi.dylib"),
            ]
        for path in candidates:
            if os.path.exists(path):
                return ctypes.cdll.LoadLibrary(path)
        raise cls._missing_library_error()

    @classmethod
    def _missing_library_error(cls):
        return FileNotFoundError(
            "hermes_runtime_abi cdylib not found in target/release; "
            "build the release artifact to enable this test"
        )

    def test_manifest_size_matches_struct(self) -> None:
        lib = self._load_library()
        lib.stable_abi_manifest_size.restype = ctypes.c_size_t
        reported_size = lib.stable_abi_manifest_size()

        class StableAbiManifest(ctypes.Structure):
            _fields_ = [
                ("abi_version_major", ctypes.c_ulonglong),
                ("abi_version_minor", ctypes.c_ulonglong),
                ("language_host_len", ctypes.c_ulonglong),
                ("language_host", ctypes.c_char_p),
                ("protocol_version_major", ctypes.c_ulonglong),
                ("protocol_version_minor", ctypes.c_ulonglong),
                ("capabilities_hot_reload", ctypes.c_int),
                ("capabilities_durable_atomics", ctypes.c_int),
                ("capabilities_capability_tokens", ctypes.c_int),
                ("capabilities_checksum_algorithm_len", ctypes.c_ulonglong),
                ("capabilities_checksum_algorithm", ctypes.c_char_p),
            ]

        self.assertEqual(reported_size, ctypes.sizeof(StableAbiManifest))

    def test_round_trip_manifest_values(self) -> None:
        lib = self._load_library()

        class StableAbiManifest(ctypes.Structure):
            _fields_ = [
                ("abi_version_major", ctypes.c_ulonglong),
                ("abi_version_minor", ctypes.c_ulonglong),
                ("language_host_len", ctypes.c_ulonglong),
                ("language_host", ctypes.c_char_p),
                ("protocol_version_major", ctypes.c_ulonglong),
                ("protocol_version_minor", ctypes.c_ulonglong),
                ("capabilities_hot_reload", ctypes.c_int),
                ("capabilities_durable_atomics", ctypes.c_int),
                ("capabilities_capability_tokens", ctypes.c_int),
                ("capabilities_checksum_algorithm_len", ctypes.c_ulonglong),
                ("capabilities_checksum_algorithm", ctypes.c_char_p),
            ]

        manifest = StableAbiManifest()
        lib.stable_abi_manifest_round_trip(ctypes.byref(manifest))
        self.assertEqual((manifest.abi_version_major, manifest.abi_version_minor), (1, 0))
        self.assertEqual((manifest.protocol_version_major, manifest.protocol_version_minor), (1, 0))
        self.assertEqual(manifest.capabilities_hot_reload, 1)
        self.assertEqual(manifest.capabilities_durable_atomics, 1)
        self.assertEqual(manifest.capabilities_capability_tokens, 1)

    def test_worker_status_default_zeros_fields(self) -> None:
        lib = self._load_library()

        class WorkerStatusAbi(ctypes.Structure):
            _fields_ = [
                ("status_code", ctypes.c_int),
                ("reloads_total", ctypes.c_ulonglong),
                ("last_reload_success", ctypes.c_int),
            ]

        status = WorkerStatusAbi()
        lib.stable_abi_worker_status_default(ctypes.byref(status))
        self.assertEqual(status.status_code, 0)
        self.assertEqual(status.reloads_total, 0)
        self.assertEqual(status.last_reload_success, 0)

    def test_capability_default_zeros_fields(self) -> None:
        lib = self._load_library()

        class CapabilityAbi(ctypes.Structure):
            _fields_ = [
                ("granted", ctypes.c_int),
                ("expires_at_ms", ctypes.c_ulonglong),
            ]

        capability = CapabilityAbi()
        lib.stable_abi_capability_default(ctypes.byref(capability))
        self.assertEqual(capability.granted, 0)
        self.assertEqual(capability.expires_at_ms, 0)


if __name__ == '__main__':
    unittest.main()
