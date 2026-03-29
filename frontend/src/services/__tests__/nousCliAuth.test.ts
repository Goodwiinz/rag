import { buildNousCliAuthPayload } from '@/services/nousCliAuth';

describe('buildNousCliAuthPayload', () => {
  it('falls back to user.organization_id when organization is missing', () => {
    const payload = buildNousCliAuthPayload({
      token: 'access-token',
      refreshTokenValue: 'refresh-token',
      tokenExpiresAt: 123,
      refreshExpiresAt: 456,
      rememberMe: true,
      organization: null,
      user: {
        email: 'admin@multimodal-rag.com',
        organization_id: 'org-from-user',
        organization_name: 'Org From User',
      },
    });

    expect(payload.organization_id).toBe('org-from-user');
    expect(payload.organization_name).toBe('Org From User');
    expect(payload.user_email).toBe('admin@multimodal-rag.com');
  });
});
