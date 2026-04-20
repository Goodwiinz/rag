import { toolLabel } from '../toolLabels';

describe('toolLabel', () => {
  it.each([
    ['arxiv_search', 'Search arXiv'],
    ['arxiv_ingest', 'Ingest papers'],
    ['document_search', 'Search documents'],
    ['ingest_document', 'Ingest document'],
    ['create_draft', 'Draft synthesis'],
    ['create_note', 'Save note'],
    ['entity_search', 'Query entities'],
    ['kg_query', 'Query knowledge graph'],
    ['project_create', 'Create project'],
    ['compare_documents', 'Compare documents'],
    ['reflect', 'Reflect on progress'],
  ])('maps %s → %s', (tool, expected) => {
    expect(toolLabel(tool)).toBe(expected);
  });

  it('falls back to Title Case for unknown tools', () => {
    expect(toolLabel('foo_bar_baz')).toBe('Foo Bar Baz');
  });

  it('leaves single-word tools as Title Case', () => {
    expect(toolLabel('ponder')).toBe('Ponder');
  });
});
