import { describe, it, expect } from 'vitest';
import { AtomicState, createReloadEvent, ReloadRegistry } from '../src/atomic_state';
import { createTask, TaskRegistry, TaskStatus } from '../src/agentic';

describe('runtime contracts', () => {
  it('atomic state put/get/cas', () => {
    const state = new AtomicState<string>();
    state.put('mode', 'agentic');
    expect(state.get('mode')).toBe('agentic');
    expect(state.compareSwap('mode', 'agentic', 'multi-lang')).toBe(true);
    expect(state.get('mode')).toBe('multi-lang');
  });

  it('reload event carries worker and checksum', () => {
    const event = createReloadEvent('python-worker', '/src/main.py', 'deadbeef');
    expect(event.workerId).toBe('python-worker');
    expect(event.checksum).toBe('deadbeef');
  });

  it('task registry persists tasks', () => {
    const registry = new TaskRegistry();
    const task = createTask('cli', 'improve', { target: 'self' });
    registry.put(task);
    expect(registry.get(task.id)?.status).toBe(TaskStatus.Queued);
  });
});
