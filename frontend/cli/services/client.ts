import { loadConfig } from '../auth/store';

export function getCliAuthHeaders(): Record<string, string> {
  const config = loadConfig();
  if (!config) throw new Error('Not logged in. Run: ./nous login');
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${config.token}`,
    'X-Organization-ID': config.organization_id,
  };
}

const DEFAULT_API_BASE = 'http://localhost:8000/api/v1';

export function getApiBase(): string {
  if (process.env.NOUS_API_URL) return process.env.NOUS_API_URL;
  const config = loadConfig();
  if (config?.api_url) return config.api_url;
  return DEFAULT_API_BASE;
}

export const API_BASE = getApiBase();
