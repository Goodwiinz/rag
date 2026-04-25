// frontend/cli/__tests__/auth/deviceFlow.test.ts
import { mergeLoginResult, pollForApproval } from '../../auth/deviceFlow';
import type { NousConfig } from '../../auth/store';

test('resolves with token when status becomes approved', async () => {
  let callCount = 0;
  const mockFetch = jest.fn().mockImplementation(() => {
    callCount++;
    const status = callCount >= 3 ? 'approved' : 'pending';
    const extra =
      status === 'approved'
        ? {
            token: 'tok_approved',
            user_email: 'a@b.com',
            organization_id: 'org1',
            expires_at: '2099-01-01T00:00:00Z',
          }
        : {};
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ status, ...extra }),
    });
  });

  const result = await pollForApproval('sess_1', 'pt_1', {
    fetchFn: mockFetch as any,
    intervalMs: 0,
  });
  expect(result.token).toBe('tok_approved');
  expect(callCount).toBe(3);
});

test('rejects when status is expired', async () => {
  const mockFetch = jest.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ status: 'expired' }),
  });
  await expect(
    pollForApproval('sess_1', 'pt_1', {
      fetchFn: mockFetch as any,
      intervalMs: 0,
    })
  ).rejects.toThrow('expired');
});

const APPROVAL = {
  token: 'tok_new',
  user_email: 'a@b.com',
  organization_id: 'org_1',
  expires_at: '2099-01-01T00:00:00Z',
};

const EXISTING: NousConfig = {
  token: 'tok_old',
  user_email: 'a@b.com',
  organization_id: 'org_1',
  expires_at: '2098-01-01T00:00:00Z',
  thread_id: 'thread-abc',
  api_url: 'https://dev-api.gen-text.app/api/v1',
};

test('mergeLoginResult preserves thread_id and api_url for same identity', () => {
  const merged = mergeLoginResult(APPROVAL, EXISTING, 'http://default/api/v1');
  expect(merged.token).toBe('tok_new');
  expect(merged.thread_id).toBe('thread-abc');
  expect(merged.api_url).toBe('https://dev-api.gen-text.app/api/v1');
});

test('mergeLoginResult clears thread_id when email differs', () => {
  const merged = mergeLoginResult(
    APPROVAL,
    { ...EXISTING, user_email: 'someone-else@b.com' },
    'http://default/api/v1'
  );
  expect(merged.thread_id).toBeNull();
});

test('mergeLoginResult clears thread_id when organization differs', () => {
  const merged = mergeLoginResult(
    APPROVAL,
    { ...EXISTING, organization_id: 'org_2' },
    'http://default/api/v1'
  );
  expect(merged.thread_id).toBeNull();
});

test('mergeLoginResult uses default api_url when no existing config', () => {
  const merged = mergeLoginResult(APPROVAL, null, 'http://default/api/v1');
  expect(merged.api_url).toBe('http://default/api/v1');
  expect(merged.thread_id).toBeNull();
});
