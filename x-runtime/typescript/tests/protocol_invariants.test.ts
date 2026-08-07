import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

const FIXTURES_DIR = path.resolve('../protocol/v1/schema');

function loadSchema(name: string): any {
  return JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, name), 'utf8'));
}

describe('TypeScript protocol invariant coverage', () => {
  it('envelope base defines core fields with stable names', () => {
    const base = loadSchema('envelope-base.json');
    const required = base.required;
    expect(required).toEqual(['protocol_version', 'message_id', 'timestamp', 'type']);
    const props = base.properties;
    expect(props.protocol_version.type).toBe('string');
    expect(props.protocol_version.pattern).toBe('^[0-9]+\\.[0-9]+$');
    expect(props.message_id.type).toBe('string');
    expect(props.timestamp.type).toBe('integer');
    expect(props.type.type).toBe('string');
  });

  it('message schemas extend envelope base with stable required extensions', () => {
    const cases: Array<{file: string; required: string[]}> = [
      {file: 'handshake.json', required: ['worker_id', 'worker_type', 'capabilities']},
      {file: 'ready.json', required: ['worker_id', 'status', 'features']},
      {file: 'reload-request.json', required: ['reload_id', 'path', 'checksum']},
      {file: 'reload-completed.json', required: ['reload_id', 'status', 'checksum']},
      {file: 'shutdown.json', required: ['grace_ms']},
      {file: 'task-submit.json', required: ['task_id', 'method']},
      {file: 'task-result.json', required: ['task_id', 'ok', 'result', 'latency_ms']},
    ];

    for (const c of cases) {
      const schema = loadSchema(c.file);
      const extension = schema.allOf[1];
      expect(extension.required, `${c.file}: required mismatch`).toEqual(c.required);
      expect(extension.properties.type.const, `${c.file}: type const mismatch`).toBeDefined();
    }
  });

  it('reload-request preserves schema shape for compatibility', () => {
    const schema = loadSchema('reload-request.json');
    const props = schema.allOf[1].properties;
    expect(props.reload_id.type).toBe('integer');
    expect(props.path.type).toBe('string');
    expect(props.checksum.type).toBe('string');
    expect(props.reload_id.minimum).toBe(0);
  });

  it('task-result exposes stable ok/result/latency_ms contract', () => {
    const schema = loadSchema('task-result.json');
    const props = schema.allOf[1].properties;
    expect(props.ok.type).toBe('boolean');
    expect(props.result.type).toBe('object');
    expect(props.latency_ms.type).toBe('integer');
    expect(props.latency_ms.minimum).toBe(0);
  });
});
