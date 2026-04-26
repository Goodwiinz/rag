/**
 * @jest-environment node
 */
import { fetchThreadMessages, fetchThreads } from '../../services/threads';
import * as client from '../../services/client';

jest.mock('../../services/client');

const mockedHeaders = client.getCliAuthHeaders as jest.MockedFunction<
  typeof client.getCliAuthHeaders
>;
const mockedBase = client.getApiBase as jest.MockedFunction<
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

afterEach(() => jest.clearAllMocks());

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

describe('fetchThreads', () => {
  test('returns the threads array on success', async () => {
    const fetchFn = jest.fn().mockResolvedValue(
      jsonResponse({
        threads: [
          {
            id: 'a',
            title: 'A',
            created_at: '',
            updated_at: '',
            message_count: 1,
            last_message_at: null,
            source_project_id: null,
            status: 'active',
            conversation_id: 'c1',
          },
        ],
        total: 1,
      })
    );
    const out = await fetchThreads({ fetchFn: fetchFn as never });
    expect(out).toHaveLength(1);
    expect(out[0].id).toBe('a');
    expect(fetchFn).toHaveBeenCalledWith(
      'http://api.test/api/v1/agent/threads',
      expect.objectContaining({ method: 'GET' })
    );
  });

  test('returns empty array when payload omits threads', async () => {
    const fetchFn = jest.fn().mockResolvedValue(jsonResponse({}));
    const out = await fetchThreads({ fetchFn: fetchFn as never });
    expect(out).toEqual([]);
  });

  test('throws on non-ok response', async () => {
    const fetchFn = jest.fn().mockResolvedValue(jsonResponse({}, 500));
    await expect(fetchThreads({ fetchFn: fetchFn as never })).rejects.toThrow(
      /500/
    );
  });
});

describe('fetchThreadMessages', () => {
  test('returns messages array on success', async () => {
    const fetchFn = jest.fn().mockResolvedValue(
      jsonResponse({
        messages: [
          {
            id: 'm1',
            role: 'user',
            content: 'hi',
            created_at: '',
            tool_name: null,
            tool_call_id: null,
            citations: null,
            tool_executions: null,
          },
        ],
        total: 1,
      })
    );
    const out = await fetchThreadMessages('thread_abc', {
      fetchFn: fetchFn as never,
    });
    expect(out).toHaveLength(1);
    expect(fetchFn).toHaveBeenCalledWith(
      'http://api.test/api/v1/agent/threads/thread_abc/messages',
      expect.objectContaining({ method: 'GET' })
    );
  });

  test('translates 404 into "Thread not found"', async () => {
    const fetchFn = jest.fn().mockResolvedValue(jsonResponse({}, 404));
    await expect(
      fetchThreadMessages('missing', { fetchFn: fetchFn as never })
    ).rejects.toThrow(/Thread not found/);
  });

  test('url-encodes the thread id', async () => {
    const fetchFn = jest.fn().mockResolvedValue(jsonResponse({ messages: [] }));
    await fetchThreadMessages('weird/id', { fetchFn: fetchFn as never });
    expect(fetchFn).toHaveBeenCalledWith(
      'http://api.test/api/v1/agent/threads/weird%2Fid/messages',
      expect.any(Object)
    );
  });
});
