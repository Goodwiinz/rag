import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import * as os from 'os';
import * as path from 'path';

export interface ThreadEntry {
  id: string;
  title: string;
  preview: string;
  project_id: string | null;
  project_name: string | null;
  last_used_at: string;
}

const MAX_STORED = 100;

function storeDir(): string {
  return process.env.NOUS_CONFIG_DIR ?? path.join(os.homedir(), '.nous');
}

function storePath(): string {
  return path.join(storeDir(), 'threads.json');
}

function readStore(): ThreadEntry[] {
  const p = storePath();
  if (!existsSync(p)) return [];
  try {
    return JSON.parse(readFileSync(p, 'utf-8')) as ThreadEntry[];
  } catch {
    return [];
  }
}

function writeStore(entries: ThreadEntry[]): void {
  const dir = storeDir();
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  writeFileSync(storePath(), JSON.stringify(entries, null, 2), 'utf-8');
}

export function getThread(id: string): ThreadEntry | undefined {
  return readStore().find((e) => e.id === id);
}

export function listThreads(): ThreadEntry[] {
  return readStore().sort((a, b) => b.last_used_at.localeCompare(a.last_used_at));
}

export function upsertThread(partial: Partial<ThreadEntry> & { id: string }): void {
  const store = readStore();
  const idx = store.findIndex((e) => e.id === partial.id);
  if (idx >= 0) {
    store[idx] = { ...store[idx], ...partial };
  } else {
    store.unshift({
      id: partial.id,
      title: partial.title ?? '(untitled)',
      preview: partial.preview ?? '',
      project_id: partial.project_id ?? null,
      project_name: partial.project_name ?? null,
      last_used_at: partial.last_used_at ?? new Date().toISOString(),
    });
  }
  writeStore(store.slice(0, MAX_STORED));
}

export function touchThread(id: string): void {
  upsertThread({ id, last_used_at: new Date().toISOString() });
}

export function removeThread(id: string): boolean {
  const store = readStore();
  const next = store.filter((e) => e.id !== id);
  if (next.length === store.length) return false;
  writeStore(next);
  return true;
}

export function reconcileThreads(remoteIds: string[]): void {
  const ids = new Set(remoteIds);
  const store = readStore().filter((e) => ids.has(e.id));
  writeStore(store);
}

export function deriveTitle(text: string): string {
  const cleaned = text.trim().replace(/\s+/g, ' ');
  const first = cleaned.split(/[.?!]/)[0]?.trim() ?? cleaned;
  return first.length > 60 ? `${first.slice(0, 57)}…` : first || '(untitled)';
}

export function derivePreview(text: string): string {
  const cleaned = text.trim().replace(/\s+/g, ' ');
  return cleaned.length > 120 ? `${cleaned.slice(0, 117)}…` : cleaned;
}
