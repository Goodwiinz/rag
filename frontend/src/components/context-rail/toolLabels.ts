export function toolLabel(tool: string): string {
  const known: Record<string, string> = {
    arxiv_search: 'Search arXiv',
  };
  return known[tool] ?? tool.replace(/_/g, ' ');
}
