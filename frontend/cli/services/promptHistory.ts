import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import * as os from 'os';
import * as path from 'path';

const FILE = 'prompt_history';
const MAX_HISTORY = 500;

function configDir(): string {
  return process.env.NOUS_CONFIG_DIR ?? path.join(os.homedir(), '.nous');
}

function filePath(): string {
  return path.join(configDir(), FILE);
}

function ensureDir(): void {
  const dir = configDir();
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

export function loadHistory(): string[] {
  try {
    if (!existsSync(filePath())) return [];
    const raw = readFileSync(filePath(), 'utf-8');
    return raw.split('\n').filter((l) => l.length > 0);
  } catch {
    return [];
  }
}

export function appendHistory(line: string): void {
  const trimmed = line.trim();
  if (!trimmed) return;
  const cur = loadHistory();
  if (cur[cur.length - 1] === trimmed) return;
  cur.push(trimmed);
  const capped = cur.slice(-MAX_HISTORY);
  ensureDir();
  writeFileSync(filePath(), capped.join('\n') + '\n', 'utf-8');
}

export function clearHistory(): void {
  ensureDir();
  writeFileSync(filePath(), '', 'utf-8');
}
