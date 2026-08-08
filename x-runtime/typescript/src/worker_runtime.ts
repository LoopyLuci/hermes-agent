import { WorkerId, WorkerCallEnvelope } from './protocols';

export interface PluginRuntimeOptions {
  name: string;
  endpoint?: string;
}

export class WorkerRuntime {
  constructor(public readonly workerId: WorkerId, private readonly options: PluginRuntimeOptions) {}

  call<T = unknown>(method: string, params: unknown, timeoutMs = 15000): Promise<T> {
    const envelope: WorkerCallEnvelope = {
      workerId: this.workerId,
      method,
      params,
      requestId: `call-${crypto.randomUUID()}`,
      timeoutMs,
    };

    return new Promise<T>((resolve, reject) => {
      // This is an integration seam: swap with a real transport later.
      void Promise.resolve({ envelope });
      resolve(undefined as T);
    });
  }
}
