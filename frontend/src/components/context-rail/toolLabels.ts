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

export function toolLabel(tool: string): string {
  if (KNOWN_TOOLS[tool]) return KNOWN_TOOLS[tool];
  return tool
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
