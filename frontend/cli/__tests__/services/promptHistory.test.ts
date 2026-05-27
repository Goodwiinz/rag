/**
 * @vitest-environment node
 */
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { mkdtempSync, rmSync } from 'fs';
import * as os from 'os';
import * as path from 'path';

describe('promptHistory', () => {
  let tmpDir: string;
  let store: typeof import('../../services/promptHistory');

  beforeEach(async () => {
    tmpDir = mkdtempSync(path.join(os.tmpdir(), 'nous-prompthistory-'));
    process.env.NOUS_CONFIG_DIR = tmpDir;
    vi.resetModules();
    store = await import('../../services/promptHistory');
  });

  afterEach(() => {
    delete process.env.NOUS_CONFIG_DIR;
    rmSync(tmpDir, { recursive: true, force: true });
  });

  test('returns empty when file is missing', () => {
    expect(store.loadHistory()).toEqual([]);
  });

  test('appends and reads back entries in order', () => {
    store.appendHistory('first');
    store.appendHistory('second');
    store.appendHistory('third');
    expect(store.loadHistory()).toEqual(['first', 'second', 'third']);
  });

  test('skips consecutive duplicates and empty lines', () => {
    store.appendHistory('a');
    store.appendHistory('a');
    store.appendHistory('   ');
    store.appendHistory('b');
    expect(store.loadHistory()).toEqual(['a', 'b']);
  });

  test('caps entries at 500', () => {
    for (let i = 0; i < 600; i++) store.appendHistory(`q${i}`);
    const out = store.loadHistory();
    expect(out).toHaveLength(500);
    expect(out[0]).toBe('q100');
    expect(out[out.length - 1]).toBe('q599');
  });

  test('clearHistory empties the file', () => {
    store.appendHistory('one');
    store.clearHistory();
    expect(store.loadHistory()).toEqual([]);
  });
});
