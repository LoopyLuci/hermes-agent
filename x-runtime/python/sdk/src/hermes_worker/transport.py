"""Zero-copy local transport via memory-mapped ring buffer."""
from __future__ import annotations

import mmap
import os
import struct
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional


RING_MAGIC = b"HMRING00"
RING_VERSION = 1
HEADER_SIZE = 128
MIN_CAPACITY = 4096
ALIGN = 64


@dataclass
class TransportCapabilities:
    supports_zero_copy: bool = True
    max_message_bytes: int = 4096
    ring_pages: int = 1


class ZeroCopyRing:
    def __init__(self, path: Path | str, capacity: int = MIN_CAPACITY) -> None:
        self.path = Path(path)
        self.capacity = max(MIN_CAPACITY, capacity)
        self._lock = threading.Lock()
        self._mm: Optional[mmap.mmap] = None
        self._create()

    def _create(self) -> None:
        fd = os.open(str(self.path), os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        try:
            ring_size = HEADER_SIZE + self.capacity
            os.ftruncate(fd, ring_size)
            self._mm = mmap.mmap(fd, ring_size)
            self._write_header(ring_size)
        finally:
            os.close(fd)

    def _write_header(self, ring_size: int) -> None:
        if self._mm is None:
            raise RuntimeError("mmap not initialized")
        self._mm.seek(0)
        self._mm.write(RING_MAGIC)
        self._mm.write(struct.pack("<I", RING_VERSION))
        self._mm.write(struct.pack("<I", 0))
        self._mm.write(struct.pack("<Q", ring_size))
        self._mm.write(struct.pack("<I", self.capacity))
        self._mm.write(struct.pack("<I", 0))
        self._mm.write(struct.pack("<I", 0))
        self._mm.write(struct.pack("<I", 0))
        self._mm.write(struct.pack("<Q", 0))
        self._mm.write(struct.pack("<I", 1))
        self._mm.write(b"\x00" * (HEADER_SIZE - 40))

    @classmethod
    def open(cls, path: Path | str) -> ZeroCopyRing:
        path = Path(path)
        fd = os.open(str(path), os.O_RDWR)
        try:
            size = os.fstat(fd).st_size
            if size < HEADER_SIZE + MIN_CAPACITY:
                raise RuntimeError("ring too small")
            mm = mmap.mmap(fd, size)
            magic = mm.read(8)
            version = struct.unpack("<I", mm.read(4))[0]
            if magic != RING_MAGIC or version != RING_VERSION:
                raise RuntimeError("invalid ring magic/version")
            mm.seek(24)
            capacity = struct.unpack("<I", mm.read(4))[0]
            ring = object.__new__(cls)
            ring.path = path
            ring.capacity = capacity
            ring._lock = threading.Lock()
            ring._mm = mm
            return ring
        finally:
            os.close(fd)

    def send(self, payload: bytes) -> None:
        if len(payload) > self.capacity - 4:
            raise ValueError("payload too large")
        with self._lock:
            if self._mm is None:
                raise RuntimeError("mmap not initialized")
            head = struct.unpack("<I", self._mm[32:36])[0]
            tail = struct.unpack("<I", self._mm[36:40])[0]
            closed = struct.unpack("<I", self._mm[40:44])[0]
            if closed:
                raise RuntimeError("ring closed")
            needed = 4 + len(payload)
            free = (self.capacity - 1 - ((head - tail) % self.capacity)) % self.capacity
            if free < needed:
                raise RuntimeError("ring full")
            offset = HEADER_SIZE + (head % self.capacity)
            if offset + needed > HEADER_SIZE + self.capacity:
                chunk = HEADER_SIZE + self.capacity - offset
                self._mm[offset:offset + chunk] = payload[:chunk] + struct.pack("<I", len(payload))
                self._mm[HEADER_SIZE:HEADER_SIZE + needed - chunk] = b"\x00" * (needed - chunk - 4) + payload[chunk - needed:]
            else:
                self._mm[offset:offset + 4] = struct.pack("<I", len(payload))
                self._mm[offset + 4:offset + needed] = payload
            self._mm[32:36] = struct.pack("<I", (head + needed) % self.capacity)

    def receive(self) -> bytes:
        with self._lock:
            if self._mm is None:
                raise RuntimeError("mmap not initialized")
            head = struct.unpack("<I", self._mm[32:36])[0]
            tail = struct.unpack("<I", self._mm[36:40])[0]
            closed = struct.unpack("<I", self._mm[40:44])[0]
            if closed:
                raise RuntimeError("ring closed")
            if head == tail:
                raise RuntimeError("ring empty")
            offset = HEADER_SIZE + (tail % self.capacity)
            length = struct.unpack("<I", self._mm[offset:offset + 4])[0]
            if length > self.capacity - 4:
                raise RuntimeError("invalid message length")
            if offset + 4 + length > HEADER_SIZE + self.capacity:
                first = HEADER_SIZE + self.capacity - offset - 4
                first_part = self._mm[offset + 4:HEADER_SIZE + self.capacity]
                second_part = self._mm[HEADER_SIZE:HEADER_SIZE + length - first]
                payload = first_part + second_part
            else:
                payload = bytes(self._mm[offset + 4:offset + 4 + length])
            self._mm[36:40] = struct.pack("<I", (tail + 4 + length) % self.capacity)
            return payload

    def close(self) -> None:
        with self._lock:
            if self._mm is None:
                return
            self._mm[40:44] = struct.pack("<I", 1)
            self._mm.close()
            self._mm = None
