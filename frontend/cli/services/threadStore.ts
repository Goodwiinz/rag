import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import * as os from 'os';
import * as path from 'path';

export interface ThreadEntry {
  id: string;
  title: string;
  project_id: string | null;
  project_name: string | null;
  last_used_at: string;
  preview: string;
}

export interface ThreadRegistry {
  version: 1;
  entries: ThreadEntry[];
}

const MAX_ENTRIES = 20;
const PREVIEW_MAX = 120;
const TITLE_MAX = 60;

function configDir(): string {
  return process.env.NOUS_CONFIG_DIR ?? path.join(os.homedir(), '.nous');
}

function registryPath(): string {
  return path.join(configDir(), 'threads.json');
}

function emptyRegistry(): ThreadRegistry {
  return { version: 1, entries: [] };
}

export function loadRegistry(): ThreadRegistry {
  const p = registryPath();
  if (!existsSync(p)) return emptyRegistry();
  try {
    const parsed = JSON.parse(
      readFileSync(p, 'utf-8')
    ) as Partial<ThreadRegistry>;
    if (!parsed || parsed.version !== 1 || !Array.isArray(parsed.entries)) {
      return emptyRegistry();
    }
    return { version: 1, entries: parsed.entries };
  } catch {
    return emptyRegistry();
  }
}

export function saveRegistry(registry: ThreadRegistry): void {
  const dir = configDir();
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  writeFileSync(registryPath(), JSON.stringify(registry, null, 2), 'utf-8');
}

export function listThreads(): ThreadEntry[] {
  return loadRegistry().entries;
}

export function getThread(id: string): ThreadEntry | null {
  return loadRegistry().entries.find((e) => e.id === id) ?? null;
}

interface UpsertInput {
  id: string;
  title?: string;
  project_id?: string | null;
  project_name?: string | null;
  preview?: string;
}

export function upsertThread(input: UpsertInput): ThreadEntry {
  const reg = loadRegistry();
  const now = new Date().toISOString();
  const existing = reg.entries.find((e) => e.id === input.id);

  const merged: ThreadEntry = {
    id: input.id,
    title: trim(input.title ?? existing?.title ?? '(untitled)', TITLE_MAX),
    project_id:
      input.project_id !== undefined
        ? input.project_id
        : (existing?.project_id ?? null),
    project_name:
      input.project_name !== undefined
        ? input.project_name
        : (existing?.project_name ?? null),
    last_used_at: now,
    preview: trim(input.preview ?? existing?.preview ?? '', PREVIEW_MAX),
  };

  const others = reg.entries.filter((e) => e.id !== input.id);
  const next: ThreadRegistry = {
    version: 1,
    entries: [merged, ...others].slice(0, MAX_ENTRIES),
  };
  saveRegistry(next);
  return merged;
}

export function touchThread(id: string): void {
  const reg = loadRegistry();
  const entry = reg.entries.find((e) => e.id === id);
  if (!entry) return;
  upsertThread({ id });
}

export function removeThread(id: string): boolean {
  const reg = loadRegistry();
  const next = reg.entries.filter((e) => e.id !== id);
  if (next.length === reg.entries.length) return false;
  saveRegistry({ version: 1, entries: next });
  return true;
}

export function reconcileThreads(remoteIds: Iterable<string>): ThreadEntry[] {
  const allowed = new Set(remoteIds);
  const reg = loadRegistry();
  const filtered = reg.entries.filter((e) => allowed.has(e.id));
  if (filtered.length !== reg.entries.length) {
    saveRegistry({ version: 1, entries: filtered });
  }
  return filtered;
}

export function deriveTitle(text: string): string {
  const cleaned = text.replace(/\s+/g, ' ').trim();
  if (!cleaned) return '(untitled)';
  return trim(cleaned, TITLE_MAX);
}

export function derivePreview(text: string): string {
  const cleaned = text.replace(/\s+/g, ' ').trim();
  return trim(cleaned, PREVIEW_MAX);
}

function trim(text: string, max: number): string {
  if (text.length <= max) return text;
  return `${text.slice(0, Math.max(0, max - 1))}…`;
}
