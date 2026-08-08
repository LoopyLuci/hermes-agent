"""Cross-language performance baseline for zero-copy local transport."""
from __future__ import annotations

import time

import pytest

from hermes_worker.transport import ZeroCopyRing


@pytest.fixture()
def ring(tmp_path):
    ring_path = tmp_path / "bench.ring"
    ring = ZeroCopyRing(ring_path, capacity=1_048_576)
    yield ring
    ring.close()


def _round_trip(ring, payload, iterations=2000):
    start = time.perf_counter()
    for _ in range(iterations):
        ring.send(payload)
        received = ring.receive()
        assert received == payload
    return time.perf_counter() - start


def test_small_payload_latency(ring):
    payload = b"hello-ring"
    elapsed = _round_trip(ring, payload)
    print(f"small round-trip: {elapsed:.4f}s")
    assert elapsed < 2.0


def test_large_payload_throughput(ring):
    payload = b"x" * 1024
    elapsed = _round_trip(ring, payload, iterations=500)
    print(f"large round-trip: {elapsed:.4f}s")
    assert elapsed < 2.0
