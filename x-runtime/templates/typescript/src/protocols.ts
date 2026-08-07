export type WorkerId = string;
export type ReloadId = number;
export type RequestId = string;

export enum WorkerStatus {
  Healthy = 'healthy',
  Reloading = 'reloading',
  Degraded = 'degraded',
  Stopped = 'stopped',
}

export enum ReloadStatus {
  Pending = 'pending',
  Reloading = 'reloading',
  Active = 'active',
  Failed = 'failed',
}

export interface ReloadEvent {
  id: ReloadId;
  workerId: WorkerId;
  path: string;
  checksum: string;
  status: ReloadStatus;
  startedAt: number;
}

export interface HotReloadable {
  kind: string;
  reload(event: ReloadEvent): Promise<void>;
}

export type BusEvent =
  | { kind: 'task.submitted'; handleId: string }
  | { kind: 'reload.requested'; reloadId: ReloadId; workerId: WorkerId }
  | { kind: 'worker.report'; report: WorkerReport };

export interface WorkerReport {
  workerId: WorkerId;
  status: WorkerStatus;
  message?: string;
  observedAt: number;
}

export interface WorkerCallEnvelope {
  workerId: WorkerId;
  method: string;
  params: unknown;
  requestId: RequestId;
  timeoutMs?: number;
}

export interface WorkerEnvelope {
  protocol_version: string;
  message_id: string;
  timestamp: number;
  type: string;
  worker_id?: string;
  task_id?: string;
  reload_id?: number;
  path?: string;
  checksum?: string;
  status?: string;
  features?: string[];
  params?: unknown;
  timeout_ms?: number;
  ok?: boolean;
  result?: unknown;
  latency_ms?: number;
  error?: { code: string; message: string };
}

export class WorkerTransport {
  private stdin = process.stdin;
  private stdout = process.stdout;

  constructor(opts?: { stdin?: NodeJS.ReadableStream; stdout?: NodeJS.WritableStream }) {
    if (opts?.stdin) this.stdin = opts.stdin;
    if (opts?.stdout) this.stdout = opts.stdout;
  }

  async read(): Promise<WorkerEnvelope> {
    const line = await this.readLine();
    return JSON.parse(line) as WorkerEnvelope;
  }

  async write(envelope: WorkerEnvelope): Promise<void> {
    const text = JSON.stringify(envelope);
    this.stdout.write(`${text}\n`);
  }

  private readLine(): Promise<string> {
    return new Promise((resolve, reject) => {
      let buffer = '';
      const onData = (chunk: Buffer) => {
        buffer += chunk.toString();
        const idx = buffer.indexOf('\n');
        if (idx !== -1) {
          cleanup();
          resolve(buffer.slice(0, idx));
        }
      };
      const onEnd = () => {
        cleanup();
        if (buffer.trim()) resolve(buffer.trim());
        else reject(new Error('stdin closed'));
      };
      const onError = (err: Error) => {
        cleanup();
        reject(err);
      };
      const cleanup = () => {
        this.stdin.removeListener('data', onData as any);
        this.stdin.removeListener('end', onEnd);
        this.stdin.removeListener('error', onError);
      };
      this.stdin.on('data', onData as any);
      this.stdin.on('end', onEnd);
      this.stdin.on('error', onError);
    });
  }
}
