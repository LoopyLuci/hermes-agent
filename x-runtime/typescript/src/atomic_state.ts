import { ReloadEvent, ReloadStatus } from './protocols';

export class AtomicState<T = unknown> {
  private readonly inner = new Map<string, T>();

  constructor(private readonly name = 'atomic-state') {}

  put(key: string, value: T): void {
    this.inner.set(key, value);
  }

  get(key: string): T | undefined {
    return this.inner.get(key);
  }

  compareSwap(key: string, expected: T | undefined, next: T | undefined): boolean {
    const current = this.inner.get(key);
    if (current === expected) {
      if (next === undefined) this.inner.delete(key);
      else this.inner.set(key, next);
      return true;
    }
    return false;
  }
}

export class ReloadRegistry {
  private seq = 0;
  nextId(): number {
    return ++this.seq;
  }
}

export function createReloadEvent(
  workerId: string,
  path: string,
  checksum: string,
  status: ReloadStatus = ReloadStatus.Pending,
): ReloadEvent {
  return {
    id: Date.now(),
    workerId,
    path,
    checksum,
    status,
    startedAt: Date.now(),
  };
}
