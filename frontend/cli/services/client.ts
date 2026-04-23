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

export const API_BASE =
  process.env.NOUS_API_URL ?? 'http://localhost:8000/api/v1';
