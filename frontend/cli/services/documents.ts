import { getApiBase, getCliAuthHeaders } from './client';

export interface RemoteDocumentSummary {
  id: string;
  title: string;
  filename: string;
  document_type: string;
  processing_status: string;
  tags: string[];
  content_preview: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentsClientOptions {
  fetchFn?: typeof fetch;
  signal?: AbortSignal;
  search?: string;
  limit?: number;
  documentType?: string;
}

export async function fetchDocuments(
  options: DocumentsClientOptions = {}
): Promise<RemoteDocumentSummary[]> {
  const { fetchFn = fetch, signal, search, limit = 50, documentType } = options;
  const params = new URLSearchParams();
  params.set('limit', String(limit));
  params.set('sort_by', 'updated_at');
  if (search) params.set('search', search);
  if (documentType) params.set('document_type', documentType);

  const url = `${getApiBase()}/documents?${params.toString()}`;
  const res = await fetchFn(url, {
    method: 'GET',
    headers: getCliAuthHeaders(),
    signal,
  });
  if (!res.ok) {
    throw new Error(`Failed to list documents: ${res.status}`);
  }
  const body = (await res.json()) as { documents?: RemoteDocumentSummary[] };
  return Array.isArray(body.documents) ? body.documents : [];
}

interface ProjectDocumentEntry {
  id: string;
  document_id: string;
  added_at: string | null;
  sort_order: number;
  document: {
    id: string;
    title: string | null;
    filename: string | null;
    status: string;
    created_at: string | null;
  };
}

export async function fetchProjectDocuments(
  projectId: string,
  options: { fetchFn?: typeof fetch; signal?: AbortSignal } = {}
): Promise<RemoteDocumentSummary[]> {
  const { fetchFn = fetch, signal } = options;
  const url = `${getApiBase()}/projects/${encodeURIComponent(projectId)}/documents`;
  const res = await fetchFn(url, {
    method: 'GET',
    headers: getCliAuthHeaders(),
    signal,
  });
  if (!res.ok) {
    throw new Error(`Failed to list project documents: ${res.status}`);
  }
  const body = (await res.json()) as { documents?: ProjectDocumentEntry[] };
  const entries = Array.isArray(body.documents) ? body.documents : [];
  return entries.map((entry) => ({
    id: entry.document.id,
    title: entry.document.title || entry.document.filename || entry.document.id,
    filename: entry.document.filename || '',
    document_type: '',
    processing_status: entry.document.status,
    tags: [],
    content_preview: null,
    created_at: entry.document.created_at || '',
    updated_at: entry.added_at || entry.document.created_at || '',
  }));
}

export async function fetchDocument(
  id: string,
  options: { fetchFn?: typeof fetch; signal?: AbortSignal } = {}
): Promise<RemoteDocumentSummary | null> {
  const { fetchFn = fetch, signal } = options;
  const url = `${getApiBase()}/documents/${encodeURIComponent(id)}`;
  const res = await fetchFn(url, {
    method: 'GET',
    headers: getCliAuthHeaders(),
    signal,
  });
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`Failed to fetch document: ${res.status}`);
  }
  return (await res.json()) as RemoteDocumentSummary;
}
