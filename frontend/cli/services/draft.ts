import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import * as os from 'os';
import * as path from 'path';

const FILE = 'draft.txt';

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

export function readDraft(): string {
  try {
    if (!existsSync(filePath())) return '';
    return readFileSync(filePath(), 'utf-8');
  } catch {
    return '';
  }
}

export function writeDraft(text: string): void {
  ensureDir();
  writeFileSync(filePath(), text, 'utf-8');
}

export function clearDraft(): void {
  writeDraft('');
}
