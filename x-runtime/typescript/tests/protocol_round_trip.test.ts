import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

const FIXTURES_DIR = path.resolve('../protocol/v1/schema');

function loadSchema(name: string): any {
  return JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, name), 'utf8'));
}

describe('TypeScript cross-language protocol coverage', () => {
  it('validates handshake schema structure', () => {
    const schema = loadSchema('handshake.json');
    expect(schema.title).toBe('Handshake');
    expect(schema.allOf[1].required).toContain('worker_id');
    expect(schema.allOf[1].properties.type.const).toBe('handshake');
  });

  it('validates reload request schema structure', () => {
    const schema = loadSchema('reload-request.json');
    expect(schema.title).toBe('ReloadRequest');
    expect(schema.allOf[1].required).toEqual(expect.arrayContaining(['reload_id', 'path', 'checksum']));
    expect(schema.allOf[1].properties.type.const).toBe('reload.request');
  });

  it('validates shutdown schema structure', () => {
    const schema = loadSchema('shutdown.json');
    expect(schema.title).toBe('Shutdown');
    expect(schema.allOf[1].properties.grace_ms.type).toBe('integer');
    expect(schema.allOf[1].properties.type.const).toBe('shutdown');
  });
});
