import { test, describe } from 'node:test';
import assert from 'node:assert';

const { ReloadRegistry, createReloadEvent } = await import('../../../typescript/src/atomic_state.ts');
const { AtomicState } = await import('../../../typescript/src/atomic_state.ts');
const { TaskRegistry, createTask } = await import('../../../typescript/src/agentic.ts');

describe('TypeScript runtime contracts', () => {
  test('creates atomic state and swaps values', () => {
    const state = new AtomicState<string>();
    state.put('lang', 'typescript');
    assert.strictEqual(state.get('lang'), 'typescript');
    assert.strictEqual(state.compareSwap('lang', 'typescript', 'rust'), true);
    assert.strictEqual(state.get('lang'), 'rust');
  });

  test('creates reload events', () => {
    const registry = new ReloadRegistry();
    const event = createReloadEvent('ts-worker', '/path/to/file.ts', 'abc123');
    assert.strictEqual(event.workerId, 'ts-worker');
    assert.strictEqual(event.checksum, 'abc123');
    assert.ok(registry.nextId() >= 1);
  });

  test('registers tasks', () => {
    const registry = new TaskRegistry();
    const task = createTask('owner', 'summarize', { input: 'hello' });
    registry.put(task);
    assert.strictEqual(task.status, 'queued');
    assert.ok(registry.get(task.id));
  });
});
