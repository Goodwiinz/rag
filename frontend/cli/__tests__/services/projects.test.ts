/**
 * @vitest-environment node
 */
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import type { MockedFunction } from 'vitest';
import { fetchProjects } from '../../services/projects';
import * as client from '../../services/client';

vi.mock('../../services/client');

const mockedHeaders = client.getCliAuthHeaders as MockedFunction<
  typeof client.getCliAuthHeaders
>;
const mockedBase = client.getApiBase as MockedFunction<
  typeof client.getApiBase
>;

beforeEach(() => {
  mockedHeaders.mockReturnValue({
    'Content-Type': 'application/json',
    Authorization: 'Bearer test',
    'X-Organization-ID': 'org_1',
  });
  mockedBase.mockReturnValue('http://api.test/api/v1');
});

afterEach(() => vi.clearAllMocks());

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

describe('fetchProjects', () => {
  test('returns projects array on success and uses limit query param', async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      jsonResponse({
        projects: [
          {
            id: 'proj_1',
            name: 'Alpha',
            description: null,
            project_type: 'research',
            research_status: 'active',
            document_count: 3,
            note_count: 1,
            draft_count: 0,
            updated_at: '2026-04-25T00:00:00Z',
          },
        ],
        total: 1,
      })
    );
    const out = await fetchProjects({ fetchFn: fetchFn as never });
    expect(out).toHaveLength(1);
    expect(out[0].id).toBe('proj_1');
    expect(fetchFn).toHaveBeenCalledWith(
      'http://api.test/api/v1/projects?limit=50',
      expect.objectContaining({ method: 'GET' })
    );
  });

  test('returns empty array when payload omits projects', async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse({}));
    const out = await fetchProjects({ fetchFn: fetchFn as never });
    expect(out).toEqual([]);
  });

  test('honors a custom limit', async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse({ projects: [] }));
    await fetchProjects({ fetchFn: fetchFn as never, limit: 10 });
    expect(fetchFn).toHaveBeenCalledWith(
      'http://api.test/api/v1/projects?limit=10',
      expect.any(Object)
    );
  });

  test('throws on non-ok response', async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse({}, 500));
    await expect(fetchProjects({ fetchFn: fetchFn as never })).rejects.toThrow(
      /500/
    );
  });
});
