import * as fs from "fs";
import * as path from "path";

const RING_MAGIC = Buffer.from("HMRING00");
const RING_VERSION = 1;
const HEADER_SIZE = 128;
const MIN_CAPACITY = 4096;

export interface TransportCapabilities {
  supportsZeroCopy: boolean;
  maxMessageBytes: number;
  ringPages: number;
}

export class ZeroCopyRing {
  private fd: number;
  private mmap: Buffer;
  public readonly capacity: number;
  private closed = false;

  constructor(private readonly filePath: string, capacity = MIN_CAPACITY) {
    this.capacity = Math.max(MIN_CAPACITY, capacity);
    this.fd = fs.openSync(filePath, fs.existsSync(filePath) ? "r+" : "w+");
    try {
      fs.ftruncateSync(this.fd, HEADER_SIZE + this.capacity);
      this.mmap = fs.readFileSync(filePath);
      this.writeHeader(HEADER_SIZE + this.capacity);
    } catch (error) {
      fs.closeSync(this.fd);
      throw error;
    }
  }

  private writeHeader(ringSize: number) {
    const header = Buffer.alloc(HEADER_SIZE);
    header.write(RING_MAGIC.toString("binary"), 0, "binary");
    header.writeUInt32LE(RING_VERSION, 8);
    header.writeUInt32LE(0, 12);
    header.writeBigUInt64LE(BigInt(ringSize), 16);
    header.writeUInt32LE(this.capacity, 24);
    header.writeUInt32LE(0, 28); // head
    header.writeUInt32LE(0, 32); // tail
    header.writeUInt32LE(0, 36); // closed
    header.writeBigUInt64LE(0n, 40); // error
    header.writeUInt32LE(1, 48); // supports_zero_copy
    header.writeUInt32LE(this.capacity, 52); // max_message_bytes
    header.writeUInt32LE(1, 56); // ring_pages
    fs.writeSync(this.fd, header, 0, header.length, 0);
    this.mmap = fs.readFileSync(this.filePath);
  }

  static open(filePath: string): ZeroCopyRing {
    const fd = fs.openSync(filePath, "a+");
    const size = fs.fstatSync(fd).size;
    if (size < HEADER_SIZE + MIN_CAPACITY) {
      fs.closeSync(fd);
      throw new Error("ring too small");
    }
    const mmap = fs.readFileSync(filePath);
    const magic = mmap.subarray(0, 8).toString("binary");
    const version = mmap.readUInt32LE(8);
    if (magic !== RING_MAGIC.toString("binary") || version !== RING_VERSION) {
      fs.closeSync(fd);
      throw new Error("invalid ring magic/version");
    }
    const ring = new ZeroCopyRing(filePath, 0);
    ring.fd = fd;
    ring.mmap = mmap;
    ring.capacity = mmap.readUInt32LE(24);
    return ring;
  }

  send(payload: Buffer): void {
    if (payload.length > this.capacity - 4) {
      throw new Error("payload too large");
    }
    const head = this.mmap.readUInt32LE(28);
    const tail = this.mmap.readUInt32LE(32);
    if (this.mmap.readUInt32LE(36) !== 0) {
      throw new Error("ring closed");
    }
    const needed = 4 + payload.length;
    const free = (this.capacity - 1 - ((head - tail) % this.capacity)) % this.capacity;
    if (free < needed) {
      throw new Error("ring full");
    }
    const offset = HEADER_SIZE + (head % this.capacity);
    const end = offset + needed;
    if (end <= HEADER_SIZE + this.capacity) {
      const header = Buffer.alloc(4);
      header.writeUInt32LE(payload.length, 0);
      fs.writeSync(this.fd, header, 0, 4, offset);
      fs.writeSync(this.fd, payload, 0, payload.length, offset + 4);
    } else {
      const first = HEADER_SIZE + this.capacity - offset;
      const header = Buffer.alloc(4);
      header.writeUInt32LE(payload.length, 0);
      fs.writeSync(this.fd, header, 0, 4, offset);
      fs.writeSync(this.fd, payload.subarray(0, first - 4), 0, first - 4, offset + 4);
      fs.writeSync(this.fd, payload.subarray(first - 4), 0, payload.length - (first - 4), HEADER_SIZE);
    }
    const newHead = head + needed;
    const headBuf = Buffer.alloc(4);
    headBuf.writeUInt32LE(newHead, 0);
    fs.writeSync(this.fd, headBuf, 0, 4, 28);
    this.mmap = fs.readFileSync(this.filePath);
  }

  receive(): Buffer {
    const head = this.mmap.readUInt32LE(28);
    const tail = this.mmap.readUInt32LE(32);
    if (this.mmap.readUInt32LE(36) !== 0) {
      throw new Error("ring closed");
    }
    if (head === tail) {
      throw new Error("ring empty");
    }
    const offset = HEADER_SIZE + (tail % this.capacity);
    const length = this.mmap.readUInt32LE(offset);
    if (length > this.capacity - 4) {
      throw new Error("invalid message length");
    }
    const end = offset + 4 + length;
    let payload: Buffer;
    if (end > HEADER_SIZE + this.capacity) {
      const first = HEADER_SIZE + this.capacity - offset - 4;
      payload = Buffer.concat([
        this.mmap.subarray(offset + 4, HEADER_SIZE + this.capacity),
        this.mmap.subarray(HEADER_SIZE, HEADER_SIZE + length - first),
      ]);
    } else {
      payload = this.mmap.subarray(offset + 4, offset + 4 + length);
    }
    const newTail = (tail + 4 + length) % this.capacity;
    const tailBuf = Buffer.alloc(4);
    tailBuf.writeUInt32LE(newTail, 0);
    fs.writeSync(this.fd, tailBuf, 0, 4, 32);
    this.mmap = fs.readFileSync(this.filePath);
    return Buffer.from(payload);
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    const closedBuf = Buffer.alloc(4);
    closedBuf.writeUInt32LE(1, 0);
    try {
      fs.writeSync(this.fd, closedBuf, 0, 4, 36);
    } catch {
      // ignore
    }
    try {
      fs.closeSync(this.fd);
    } catch {
      // ignore
    }
  }
}
