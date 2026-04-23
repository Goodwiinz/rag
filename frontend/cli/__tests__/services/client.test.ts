import { getCliAuthHeaders } from '../../services/client';

jest.mock('../../auth/store');

import { loadConfig } from '../../auth/store';

const mockLoadConfig = loadConfig as jest.MockedFunction<typeof loadConfig>;

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
  expect(headers['X-Organization-ID']).toBe('org_1');
});

test('throws when not logged in', () => {
  mockLoadConfig.mockReturnValue(null);
  expect(() => getCliAuthHeaders()).toThrow('Not logged in');
});
