"""Tests for hermes_bridges.bridge."""
from __future__ import annotations

import unittest
from pathlib import Path

from hermes_bridges.bridge import RustBridge, ClojureBridge, TypeScriptBridge, BridgeSettings
from hermes_bridges.bridge.hot_reload_watcher import sha256_of


class BridgeStatusTests(unittest.TestCase):
    def test_rust_bridge_status(self) -> None:
        settings = BridgeSettings(
            repo_root=Path(".").resolve(),
            atomic_module_dir=Path("x-runtime/rust/atomic/target/release"),
        )
        status = RustBridge(settings).status()
        self.assertIn("rust", status)

    def test_clojure_bridge_status(self) -> None:
        settings = BridgeSettings(
            repo_root=Path(".").resolve(),
            atomic_module_dir=Path("x-runtime/rust/atomic/target/release"),
        )
        status = ClojureBridge(settings).status()
        self.assertIn("clojure", status)

    def test_typescript_bridge_status(self) -> None:
        settings = BridgeSettings(
            repo_root=Path(".").resolve(),
            atomic_module_dir=Path("x-runtime/rust/atomic/target/release"),
        )
        status = TypeScriptBridge(settings).status()
        self.assertIn("typescript", status)


class ChecksumTests(unittest.TestCase):
    def test_sha256_of(self) -> None:
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            handle.write(b"hello")
            path = Path(handle.name)
        try:
            digest = sha256_of(path)
            self.assertEqual(digest, "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
