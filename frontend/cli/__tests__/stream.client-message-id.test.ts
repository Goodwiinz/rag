/**
 * @vitest-environment node
 */
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import type { MockedFunction } from 'vitest';
import { streamAgent } from '../stream';
import * as store from '../auth/store';
import * as client from '../services/client';

vi.mock('../auth/store');
vi.mock('../services/client');

const mockedLoadConfig = store.loadConfig as MockedFunction<
  typeof store.loadConfig
>;
const mockedGetHeaders = client.getCliAuthHeaders as MockedFunction<
  typeof client.getCliAuthHeaders
>;

const CONFIG = {
  token: 'tok_test',
  user_email: 'a@b.com',
  organization_id: 'org_1',
  expires_at: '2099-01-01T00:00:00Z',
  thread_id: null,
};

const HEADERS = {
  'Content-Type': 'application/json',
  Authorization: 'Bearer tok_test',
  'X-Organization-ID': 'org_1',
};

const UUID_V4_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

beforeEach(() => {
  mockedLoadConfig.mockReturnValue(CONFIG);
  mockedGetHeaders.mockReturnValue(HEADERS);
});

afterEach(() => vi.clearAllMocks());

test('streamAgent sends a UUID v4 client_message_id on the user message', async () => {
  const fetchSpy = vi
    .fn()
    .mockResolvedValue({ ok: true, status: 200, body: null });

  const gen = streamAgent('hi', {}, { fetchFn: fetchSpy as never });
  // Drain so the fetch + early-return path executes.
  for await (const _ of gen) {
    // ignore events
  }

  expect(fetchSpy).toHaveBeenCalledTimes(1);
  const body = JSON.parse(fetchSpy.mock.calls[0][1].body);
  expect(Array.isArray(body.messages)).toBe(true);
  expect(body.messages[0].role).toBe('user');
  expect(body.messages[0].content).toBe('hi');
  expect(body.messages[0].client_message_id).toMatch(UUID_V4_RE);
});
