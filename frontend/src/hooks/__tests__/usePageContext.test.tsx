import { renderHook } from '@testing-library/react';

// Mock next/navigation
const mockPathname = jest.fn<string, []>();
jest.mock('next/navigation', () => ({
  usePathname: () => mockPathname(),
  useParams: () => ({}),
}));

// Mock project store
const mockCurrentProject = jest.fn();
jest.mock('@/store/projectStore', () => ({
  useProjectStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({ currentProject: mockCurrentProject() }),
}));

import { usePageContext } from '@/hooks/usePageContext';

describe('usePageContext', () => {
  beforeEach(() => {
    mockPathname.mockReturnValue('/');
    mockCurrentProject.mockReturnValue(null);
  });

  it('returns overview context for root path', () => {
    mockPathname.mockReturnValue('/');
    const { result } = renderHook(() => usePageContext());
    expect(result.current.type).toBe('overview');
  });

  it('returns documents context for /documents', () => {
    mockPathname.mockReturnValue('/documents');
    const { result } = renderHook(() => usePageContext());
    expect(result.current.type).toBe('documents');
    expect(result.current.label).toBe('Documents');
  });

  it('returns arxiv context for /arxiv', () => {
    mockPathname.mockReturnValue('/arxiv');
    const { result } = renderHook(() => usePageContext());
    expect(result.current.type).toBe('arxiv');
  });

  it('returns project context with project data', () => {
    mockPathname.mockReturnValue('/projects/abc-123');
    mockCurrentProject.mockReturnValue({ id: 'abc-123', name: 'My Project' });
    const { result } = renderHook(() => usePageContext());
    expect(result.current.type).toBe('project');
    expect(result.current.projectId).toBe('abc-123');
    expect(result.current.projectName).toBe('My Project');
  });

  it('returns chat context for /chat', () => {
    mockPathname.mockReturnValue('/chat');
    const { result } = renderHook(() => usePageContext());
    expect(result.current.type).toBe('chat');
  });

  it('returns unknown for unrecognized paths', () => {
    mockPathname.mockReturnValue('/something-random');
    const { result } = renderHook(() => usePageContext());
    expect(result.current.type).toBe('unknown');
  });
});
