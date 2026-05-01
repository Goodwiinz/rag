/**
 * @vitest-environment node
 */
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { mkdtempSync, rmSync, writeFileSync } from 'fs';
import * as os from 'os';
import * as path from 'path';

describe('draft store', () => {
  let tmp: string;
  let store: typeof import('../../services/draft');

  beforeEach(async () => {
    tmp = mkdtempSync(path.join(os.tmpdir(), 'nous-draft-'));
    process.env.NOUS_CONFIG_DIR = tmp;
    vi.resetModules();
    store = await import('../../services/draft');
  });

  afterEach(() => {
    delete process.env.NOUS_CONFIG_DIR;
    rmSync(tmp, { recursive: true, force: true });
  });

  test('readDraft returns empty string when missing', () => {
    expect(store.readDraft()).toBe('');
  });

  test('writeDraft + readDraft round-trips multiline content', () => {
    store.writeDraft('hello\nworld');
    expect(store.readDraft()).toBe('hello\nworld');
  });

  test('writeDraft with empty string clears the file', () => {
    store.writeDraft('seed');
    store.writeDraft('');
    expect(store.readDraft()).toBe('');
  });

  test('clearDraft empties the file', () => {
    store.writeDraft('something');
    store.clearDraft();
    expect(store.readDraft()).toBe('');
  });

  test('readDraft survives a malformed (non-utf8) file gracefully', () => {
    writeFileSync(path.join(tmp, 'draft.txt'), Buffer.from([0xff, 0xfe]));
    // Should not throw; content may be replacement chars but type is string
    expect(typeof store.readDraft()).toBe('string');
  });
});
