import { getApiBase, getCliAuthHeaders } from './client';

export interface RemoteProjectSummary {
  id: string;
  name: string;
  updated_at?: string | null;
  document_count: number;
  note_count: number;
  draft_count: number;
}

export async function fetchProjects(): Promise<RemoteProjectSummary[]> {
  const res = await fetch(`${getApiBase()}/projects/`, {
    headers: getCliAuthHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to fetch projects: ${res.status}`);
  const data = (await res.json()) as
    | { projects?: RemoteProjectSummary[]; items?: RemoteProjectSummary[] }
    | RemoteProjectSummary[];
  if (Array.isArray(data)) return data;
  return data.projects ?? data.items ?? [];
}
