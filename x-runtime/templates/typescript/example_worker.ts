import { WorkerEnvelope, WorkerTransport, HandshakeMessage } from '../src/protocols';

function uid(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function now(): number {
  return Date.now();
}

async function main() {
  const transport = new WorkerTransport();
  const handshake: HandshakeMessage = await transport.read();
  await transport.write({
    protocol_version: '1.0',
    message_id: uid(),
    timestamp: now(),
    type: 'ready',
    worker_id: handshake.worker_id,
    status: 'healthy',
    features: ['task.echo'],
  });

  while (true) {
    const msg = await transport.read();
    if (msg.type === 'task.submit') {
      await transport.write({
        protocol_version: '1.0',
        message_id: uid(),
        timestamp: now(),
        type: 'task.result',
        task_id: msg.task_id,
        ok: true,
        result: { echo: msg.params },
        latency_ms: 1,
      });
    } else if (msg.type === 'reload.request') {
      await transport.write({
        protocol_version: '1.0',
        message_id: uid(),
        timestamp: now(),
        type: 'reload.completed',
        reload_id: msg.reload_id,
        status: 'active',
        checksum: msg.checksum ?? '',
      });
    } else if (msg.type === 'shutdown') {
      process.exit(0);
    } else {
      await transport.write({
        protocol_version: '1.0',
        message_id: uid(),
        timestamp: now(),
        type: 'error',
        error: { code: 'unknown', message: `unknown type ${msg.type}` },
      });
    }
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
