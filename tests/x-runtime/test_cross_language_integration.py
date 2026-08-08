"""Cross-language integration harness: supervisor/transport/protocol/stable ABI contract."""
from __future__ import annotations

import ctypes
import os
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))


class TestCrossLanguageIntegration(unittest.TestCase):
    def _abi_candidates(self):
        if os.name == 'nt':
            names = [
                os.path.join(REPO_ROOT, 'x-runtime', 'rust', 'target', 'release', 'hermes_runtime_abi.dll'),
                os.path.join(REPO_ROOT, 'x-runtime', 'rust', 'target', 'release', 'libhermes_runtime_abi.so'),
                os.path.join(REPO_ROOT, 'x-runtime', 'rust', 'target', 'release', 'libhermes_runtime_abi.dylib'),
            ]
        elif os.name == 'darwin':
            names = [
                os.path.join(REPO_ROOT, 'x-runtime', 'rust', 'target', 'release', 'libhermes_runtime_abi.dylib'),
                os.path.join(REPO_ROOT, 'x-runtime', 'rust', 'target', 'release', 'libhermes_runtime_abi.so'),
                os.path.join(REPO_ROOT, 'x-runtime', 'rust', 'target', 'release', 'hermes_runtime_abi.dll'),
            ]
        else:
            names = [
                os.path.join(REPO_ROOT, 'x-runtime', 'rust', 'target', 'release', 'libhermes_runtime_abi.so'),
                os.path.join(REPO_ROOT, 'x-runtime', 'rust', 'target', 'release', 'hermes_runtime_abi.dll'),
                os.path.join(REPO_ROOT, 'x-runtime', 'rust', 'target', 'release', 'libhermes_runtime_abi.dylib'),
            ]
        return [p for p in names if os.path.exists(p)]

    def test_stable_abi_manifest_size_matches_python_struct(self) -> None:
        candidates = self._abi_candidates()
        if not candidates:
            self.skipTest('abi cdylib missing')
        lib = ctypes.cdll.LoadLibrary(candidates[0])
        lib.stable_abi_manifest_size.restype = ctypes.c_size_t
        reported = lib.stable_abi_manifest_size()

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

        self.assertEqual(reported, ctypes.sizeof(StableAbiManifest))

    def test_kotlin_abi_harness(self) -> None:
        import subprocess
        script = os.path.join(REPO_ROOT, "x-runtime", "kotlin", "scripts", "build.ps1" if os.name == "nt" else "build.sh")
        preloader = os.path.join(REPO_ROOT, "x-runtime", "kotlin", "dist", "kotlinc", "lib", "kotlin-preloader.jar")
        compiler = os.path.join(REPO_ROOT, "x-runtime", "kotlin", "dist", "kotlinc", "lib", "kotlin-compiler.jar")
        if not os.path.exists(script) or not os.path.exists(preloader) or not os.path.exists(compiler):
            self.skipTest("kotlin test harness prerequisites missing")
        command = ["pwsh", script, "test"] if os.name == "nt" else ["bash", script, "test"]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
