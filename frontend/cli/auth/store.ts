import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'fs';
import * as os from 'os';
import * as path from 'path';

export interface NousConfig {
  token: string;
  user_email: string;
  organization_id: string;
  expires_at: string;
  thread_id: string | null;
  api_url?: string;
}

function configDir(): string {
  return process.env.NOUS_CONFIG_DIR ?? path.join(os.homedir(), '.nous');
}

function configPath(): string {
  return path.join(configDir(), 'config.json');
}

export function loadConfig(): NousConfig | null {
  const p = configPath();
  if (!existsSync(p)) return null;
  try {
    return JSON.parse(readFileSync(p, 'utf-8')) as NousConfig;
  } catch {
    return null;
  }
}

export function saveConfig(config: NousConfig): void {
  const dir = configDir();
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  writeFileSync(configPath(), JSON.stringify(config, null, 2), 'utf-8');
}

export function clearConfig(): void {
  const p = configPath();
  if (existsSync(p)) rmSync(p);
}
