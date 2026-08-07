import { ZeroCopyRing } from "./transport";
import * as os from "os";

const RING_PATH = `${os.tmpdir()}/hermes-transport-bench-${Date.now()}.ring`;

function benchRoundTrip(iterations: number, payload: Buffer) {
  const ring = new ZeroCopyRing(RING_PATH, 1024 * 1024);
  const start = Date.now();
  for (let i = 0; i < iterations; i++) {
    ring.send(payload);
    const received = ring.receive();
    if (!received.equals(payload)) {
      throw new Error("payload mismatch");
    }
  }
  const elapsed = Date.now() - start;
  ring.close();
  try {
    require("fs").unlinkSync(RING_PATH);
  } catch {
    // ignore cleanup errors
  }
  return elapsed;
}

const small = Buffer.from("hello-ring");
const smallMs = benchRoundTrip(2000, small);
console.log(`TypeScript small round-trip: ${smallMs}ms`);
if (smallMs > 2000) {
  throw new Error("small round-trip too slow");
}

const large = Buffer.alloc(1024, 120);
const largeMs = benchRoundTrip(500, large);
console.log(`TypeScript large round-trip: ${largeMs}ms`);
if (largeMs > 2000) {
  throw new Error("large round-trip too slow");
}
