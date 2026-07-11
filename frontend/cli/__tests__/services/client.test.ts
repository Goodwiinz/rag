import { expect, test, vi } from 'vitest';
import type { MockedFunction } from 'vitest';
import { getCliAuthHeaders, safeFetch } from '../../services/client';

vi.mock('../../auth/store');

import { loadConfig } from '../../auth/store';

const mockLoadConfig = loadConfig as MockedFunction<typeof loadConfig>;

test('returns Authorization header when token is present', () => {
  mockLoadConfig.mockReturnValue({
    token: 'tok_test',
    user_email: 'x@y.com',
    organization_id: 'org_1',
    expires_at: '2099-01-01T00:00:00Z',
    thread_id: null,
  });
  const headers = getCliAuthHeaders();
  expect(headers['Authorization']).toBe('Bearer tok_test');
  // The backend derives org from the authenticated user; the dead
  // X-Organization-ID header must not be sent.
  expect(headers['X-Organization-ID']).toBeUndefined();
});

test('throws when not logged in', () => {
  mockLoadConfig.mockReturnValue(null);
  expect(() => getCliAuthHeaders()).toThrow('Not logged in');
});

test('safeFetch wraps fetch failures with the URL in the message', async () => {
  const inner = Object.assign(new Error('connect ECONNREFUSED'), {
    code: 'ECONNREFUSED',
  });
  const fetchFn = vi.fn().mockRejectedValue(inner);
  await expect(
    safeFetch('http://example.test/x', undefined, fetchFn as never)
  ).rejects.toMatchObject({
    message: expect.stringContaining('http://example.test/x'),
    code: 'ECONNREFUSED',
  });
});
