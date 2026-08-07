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
