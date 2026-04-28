import { getApiBase, getCliAuthHeaders } from './client';

export interface RemoteProjectSummary {
  id: string;
  name: string;
  description: string | null;
  project_type: string;
  research_status: string;
  document_count: number;
  note_count: number;
  draft_count: number;
  updated_at: string;
}

export interface ProjectsClientOptions {
  fetchFn?: typeof fetch;
  signal?: AbortSignal;
  limit?: number;
}

export async function fetchProjects(
  options: ProjectsClientOptions = {}
): Promise<RemoteProjectSummary[]> {
  const { fetchFn = fetch, signal, limit = 50 } = options;
  const url = `${getApiBase()}/projects?limit=${encodeURIComponent(String(limit))}`;
  const res = await fetchFn(url, {
    method: 'GET',
    headers: getCliAuthHeaders(),
    signal,
  });
  if (!res.ok) {
    throw new Error(`Failed to list projects: ${res.status}`);
  }
  const body = (await res.json()) as { projects?: RemoteProjectSummary[] };
  return Array.isArray(body.projects) ? body.projects : [];
}
