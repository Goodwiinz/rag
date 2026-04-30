import { Mock, afterEach, describe, expect, it, vi } from 'vitest';
import {
  buildNousCliAuthPayload,
  downloadStoredNousCliAuth,
} from '@/services/nousCliAuth';
import { createClient } from '@/lib/supabase/client';
import { useAuthStore } from '@/stores/authStore';

vi.mock('@/lib/supabase/client', () => ({
  createClient: vi.fn(),
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: {
    getState: vi.fn(),
  },
}));

describe('nousCliAuth', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

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

  it('builds a payload from the current Supabase session shape', () => {
    const payload = buildNousCliAuthPayload({
      session: {
        access_token: 'supabase-access-token',
        refresh_token: 'supabase-refresh-token',
        expires_at: 123,
      },
      rememberMe: false,
      refreshExpiresAt: 456,
      organization: { id: 'org-123', name: 'Acme' },
      user: {
        email: 'user@example.com',
      },
    });

    expect(payload.token).toBe('supabase-access-token');
    expect(payload.refresh_token).toBe('supabase-refresh-token');
    expect(payload.organization_id).toBe('org-123');
    expect(payload.organization_name).toBe('Acme');
    expect(payload.user_email).toBe('user@example.com');
    expect(payload.token_expires_at).toBe(123000);
    expect(payload.refresh_expires_at).toBe(456);
    expect(payload.remember_me).toBe(false);
  });

  it('downloads auth using the current Supabase session and store metadata', async () => {
    const originalCreateObjectURL = URL.createObjectURL;
    const originalRevokeObjectURL = URL.revokeObjectURL;
    const createObjectURLMock = vi.fn(() => 'blob:mock');
    const revokeObjectURLMock = vi.fn();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {});

    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      writable: true,
      value: createObjectURLMock,
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      writable: true,
      value: revokeObjectURLMock,
    });

    (useAuthStore.getState as Mock).mockReturnValue({
      organization: { id: 'org-123', name: 'Acme' },
      user: {
        email: 'user@example.com',
        organization_id: 'org-123',
      },
    });

    (createClient as Mock).mockReturnValue({
      auth: {
        getSession: vi.fn().mockResolvedValue({
          data: {
            session: {
              access_token: 'supabase-access-token',
              refresh_token: 'supabase-refresh-token',
              expires_at: 123,
            },
          },
          error: null,
        }),
      },
    });

    await downloadStoredNousCliAuth();

    expect(useAuthStore.getState).toHaveBeenCalledTimes(1);
    expect(createClient).toHaveBeenCalledTimes(1);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(createObjectURLMock).toHaveBeenCalledTimes(1);
    expect(revokeObjectURLMock).toHaveBeenCalledWith('blob:mock');

    clickSpy.mockRestore();
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      writable: true,
      value: originalCreateObjectURL,
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      writable: true,
      value: originalRevokeObjectURL,
    });
  });
});
