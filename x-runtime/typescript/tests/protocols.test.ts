import { describe, it, expect } from 'vitest';
import * as protocols from '../src/protocols';
import { AtomicState, ReloadRegistry, createReloadEvent } from '../src/atomic_state';
import { createTask, TaskRegistry, TaskStatus } from '../src/agentic';
import { WorkerRuntime } from '../src/worker_runtime';

describe('TypeScript runtime contracts', () => {
  it('exports stable protocol types', () => {
    expect(protocols.ReloadStatus.Pending).toBe('pending');
    expect(protocols.WorkerStatus.Healthy).toBe('healthy');
  });

  it('creates atomic state and swaps values', () => {
    const state = new AtomicState<string>();
    state.put('lang', 'typescript');
    expect(state.get('lang')).toBe('typescript');
    expect(state.compareSwap('lang', 'typescript', 'rust')).toBe(true);
    expect(state.get('lang')).toBe('rust');
  });

  it('creates reload events', () => {
    const registry = new ReloadRegistry();
    const event = createReloadEvent('ts-worker', '/path/to/file.ts', 'abc123');
    expect(event.workerId).toBe('ts-worker');
    expect(event.checksum).toBe('abc123');
    expect(registry.nextId()).toBeGreaterThanOrEqual(1);
  });

  it('registers tasks', () => {
    const registry = new TaskRegistry();
    const task = createTask('owner', 'summarize', { input: 'hello' });
    registry.put(task);
    expect(task.status).toBe(TaskStatus.Queued);
    expect(registry.get(task.id)).toBeDefined();
  });
});
