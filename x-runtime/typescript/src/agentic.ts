import { WorkerId } from './protocols';

export interface AgenticTask {
  id: string;
  owner: WorkerId;
  kind: string;
  input: unknown;
  output?: unknown;
  status: TaskStatus;
  createdAt: number;
  updatedAt: number;
}

export enum TaskStatus {
  Queued = 'queued',
  Running = 'running',
  Completed = 'completed',
  Failed = 'failed',
}

export function createTask(owner: WorkerId, kind: string, input: unknown): AgenticTask {
  const now = Date.now();
  return {
    id: `task-${crypto.randomUUID()}`,
    owner,
    kind,
    input,
    status: TaskStatus.Queued,
    createdAt: now,
    updatedAt: now,
  };
}

export class TaskRegistry {
  private readonly tasks = new Map<string, AgenticTask>();

  put(task: AgenticTask): void {
    this.tasks.set(task.id, task);
  }

  get(id: string): AgenticTask | undefined {
    return this.tasks.get(id);
  }
}
