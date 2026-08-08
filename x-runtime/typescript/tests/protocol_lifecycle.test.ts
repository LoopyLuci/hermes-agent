import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

const FIXTURES_DIR = path.resolve('../protocol/v1/schema');

function loadSchema(name: string): any {
  return JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, name), 'utf8'));
}

describe('TypeScript cross-language workflow lifecycle', () => {
  it('envelope base defines core fields and message schemas extend it', () => {
    const base = loadSchema('envelope-base.json');
    expect(base.required).toEqual(
      expect.arrayContaining(['protocol_version', 'message_id', 'timestamp', 'type'])
    );

    const cases = [
      { file: 'handshake.json', type: 'handshake', extraRequired: ['worker_id', 'worker_type', 'capabilities'] },
      { file: 'reload-request.json', type: 'reload.request', extraRequired: ['reload_id', 'path', 'checksum'] },
      { file: 'task-submit.json', type: 'task.submit', extraRequired: ['task_id', 'method'] },
    ];

    for (const c of cases) {
      const schema = loadSchema(c.file);
      const extension = schema.allOf[1];
      expect(extension.required).toEqual(
        expect.arrayContaining(c.extraRequired)
      );
      expect(extension.properties.type.const).toBe(c.type);
    }
  });
});
