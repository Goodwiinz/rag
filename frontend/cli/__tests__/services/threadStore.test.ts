/**
 * @vitest-environment node
 */
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { mkdtempSync, rmSync, writeFileSync } from 'fs';
import * as os from 'os';
import * as path from 'path';

describe('threadStore', () => {
  let tmpDir: string;
  let store: typeof import('../../services/threadStore');

  beforeEach(async () => {
    tmpDir = mkdtempSync(path.join(os.tmpdir(), 'nous-threadstore-'));
    process.env.NOUS_CONFIG_DIR = tmpDir;
    vi.resetModules();
    store = await import('../../services/threadStore');
  });

  afterEach(() => {
    delete process.env.NOUS_CONFIG_DIR;
    rmSync(tmpDir, { recursive: true, force: true });
  });

  test('returns empty registry when file is missing', () => {
    expect(store.listThreads()).toEqual([]);
    expect(store.getThread('anything')).toBeNull();
  });

  test('upsert adds a new thread and reads it back', () => {
    const entry = store.upsertThread({
      id: 'thread_1',
      title: 'My first prompt',
      preview: 'Hello world',
      project_id: 'proj_1',
      project_name: 'My Project',
    });
    expect(entry.title).toBe('My first prompt');
    expect(entry.project_id).toBe('proj_1');
    expect(entry.last_used_at).toMatch(/\d{4}-\d{2}-\d{2}/);

    const fetched = store.getThread('thread_1');
    expect(fetched?.id).toBe('thread_1');
    expect(fetched?.preview).toBe('Hello world');
  });

  test('upsert preserves prior fields when omitted', () => {
    store.upsertThread({
      id: 'thread_1',
      title: 'Original',
      project_id: 'proj_1',
      project_name: 'P1',
    });
    store.upsertThread({ id: 'thread_1', preview: 'new preview' });
    const fetched = store.getThread('thread_1');
    expect(fetched?.title).toBe('Original');
    expect(fetched?.project_id).toBe('proj_1');
    expect(fetched?.preview).toBe('new preview');
  });

  test('upsert moves the thread to the front (most recent first)', () => {
    store.upsertThread({ id: 'a', title: 'A' });
    store.upsertThread({ id: 'b', title: 'B' });
    store.upsertThread({ id: 'c', title: 'C' });
    store.upsertThread({ id: 'a', preview: 'updated' });

    const ids = store.listThreads().map((t) => t.id);
    expect(ids[0]).toBe('a');
  });

  test('caps registry at 20 entries', () => {
    for (let i = 0; i < 25; i++) {
      store.upsertThread({ id: `thread_${i}`, title: `T${i}` });
    }
    const entries = store.listThreads();
    expect(entries).toHaveLength(20);
    expect(entries[0].id).toBe('thread_24');
  });

  test('removeThread returns true on hit, false on miss', () => {
    store.upsertThread({ id: 'thread_1', title: 'A' });
    expect(store.removeThread('thread_1')).toBe(true);
    expect(store.removeThread('thread_1')).toBe(false);
    expect(store.listThreads()).toEqual([]);
  });

  test('reconcileThreads drops local entries not in remote set', () => {
    store.upsertThread({ id: 'a', title: 'A' });
    store.upsertThread({ id: 'b', title: 'B' });
    store.upsertThread({ id: 'c', title: 'C' });
    const kept = store.reconcileThreads(['a', 'c']);
    const ids = kept.map((e) => e.id).sort();
    expect(ids).toEqual(['a', 'c']);
    expect(
      store
        .listThreads()
        .map((e) => e.id)
        .sort()
    ).toEqual(['a', 'c']);
  });

  test('deriveTitle collapses whitespace and truncates long input', () => {
    expect(store.deriveTitle('  hello\n\nworld  ')).toBe('hello world');
    expect(store.deriveTitle('')).toBe('(untitled)');
    const long = 'x'.repeat(200);
    const title = store.deriveTitle(long);
    expect(title.length).toBeLessThanOrEqual(60);
    expect(title.endsWith('…')).toBe(true);
  });

  test('derivePreview truncates to preview max', () => {
    const long = 'a'.repeat(500);
    const preview = store.derivePreview(long);
    expect(preview.length).toBeLessThanOrEqual(120);
  });

  test('survives a corrupted registry file', () => {
    writeFileSync(path.join(tmpDir, 'threads.json'), '{not json', 'utf-8');
    expect(store.listThreads()).toEqual([]);
  });
});
