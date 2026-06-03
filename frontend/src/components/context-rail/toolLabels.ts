const KNOWN_TOOLS: Record<string, string> = {
  arxiv_search: 'Search arXiv',
  arxiv_ingest: 'Ingest papers',
  document_search: 'Search documents',
  ingest_document: 'Ingest document',
  create_draft: 'Draft synthesis',
  create_note: 'Save note',
  entity_search: 'Query entities',
  kg_query: 'Query knowledge graph',
  project_create: 'Create project',
  compare_documents: 'Compare documents',
  reflect: 'Reflect on progress',
};

// Plain present-progressive narration for active steps.
const ACTIVE_LABELS: Record<string, string> = {
  arxiv_search: 'Searching arXiv',
  arxiv_ingest: 'Ingesting papers',
  document_search: 'Searching documents',
  ingest_document: 'Ingesting document',
  create_draft: 'Drafting synthesis',
  create_note: 'Saving note',
  entity_search: 'Querying entities',
  kg_query: 'Querying the knowledge graph',
  project_create: 'Creating project',
  compare_documents: 'Comparing documents',
  reflect: 'Reflecting on progress',
};

// Past tense for completed steps.
const DONE_LABELS: Record<string, string> = {
  arxiv_search: 'Searched arXiv',
  arxiv_ingest: 'Ingested papers',
  document_search: 'Searched documents',
  ingest_document: 'Ingested document',
  create_draft: 'Drafted synthesis',
  create_note: 'Saved note',
  entity_search: 'Queried entities',
  kg_query: 'Queried the knowledge graph',
  project_create: 'Created project',
  compare_documents: 'Compared documents',
  reflect: 'Reflected on progress',
};

function humanize(tool: string): string {
  return tool.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function toolLabel(tool: string): string {
  return KNOWN_TOOLS[tool] ?? humanize(tool);
}

/**
 * Status-aware microcopy. Quiet, plain, present- or past-tense.
 * Falls back to a humanized form of the raw tool name for unknown tools.
 */
export function toolStatusLabel(
  tool: string,
  status: 'active' | 'done' | 'error'
): string {
  if (status === 'active') {
    return `${ACTIVE_LABELS[tool] ?? humanize(tool)}…`;
  }
  if (status === 'done') {
    return DONE_LABELS[tool] ?? humanize(tool);
  }
  return `${DONE_LABELS[tool] ?? humanize(tool)} (failed)`;
}
