import { beforeEach, describe, expect, it, vi } from 'vitest';
describe('useAuthStore signOut', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it('clears workspace-scoped caches when signing out', async () => {
    const mockBrowserSignOut = vi.fn().mockResolvedValue(undefined);
    const mockClearWorkspaceServiceCache = vi.fn();

    vi.doMock('@/lib/supabase/client', () => ({
      createClient: () => ({
        auth: {
          onAuthStateChange: vi.fn(),
          signOut: mockBrowserSignOut,
        },
      }),
    }));

    vi.doMock('@/services/workspaceService', () => ({
      clearWorkspaceServiceCache: mockClearWorkspaceServiceCache,
    }));

    const { useAuthStore } =
      await vi.importActual<typeof import('@/stores/authStore')>(
        '@/stores/authStore'
      );

    useAuthStore.setState({
      user: { id: 'user-1' } as any,
      organization: { id: 'org-1' } as any,
      isAuthenticated: true,
      isLoading: false,
      error: 'stale error',
      pendingEmailConfirmation: true,
    });

    useAuthStore.getState().signOut();

    expect(mockClearWorkspaceServiceCache).toHaveBeenCalledTimes(1);
    expect(mockBrowserSignOut).toHaveBeenCalledTimes(1);
    expect(useAuthStore.getState()).toEqual(
      expect.objectContaining({
        user: null,
        organization: null,
        isAuthenticated: false,
        error: null,
        pendingEmailConfirmation: false,
      })
    );
  });

  it('destroys the local auth cookie when server-side revocation fails', async () => {
    // supabase-js returns { error } WITHOUT clearing the local session when the
    // revocation request fails, so the SSR cookie would otherwise survive and
    // sign the user straight back in on the next page load.
    const mockBrowserSignOut = vi
      .fn()
      .mockResolvedValue({ error: new Error('Failed to fetch') });

    vi.doMock('@/lib/supabase/client', () => ({
      createClient: () => ({
        auth: {
          onAuthStateChange: vi.fn(),
          signOut: mockBrowserSignOut,
        },
      }),
    }));

    vi.doMock('@/services/workspaceService', () => ({
      clearWorkspaceServiceCache: vi.fn(),
    }));

    const { useAuthStore } =
      await vi.importActual<typeof import('@/stores/authStore')>(
        '@/stores/authStore'
      );

    document.cookie = 'sb-example-auth-token=chunkless-session; Path=/';
    document.cookie = 'sb-example-auth-token.0=first-chunk; Path=/';
    document.cookie = 'unrelated-cookie=keep-me; Path=/';
    expect(document.cookie).toContain('sb-example-auth-token=');

    await expect(useAuthStore.getState().signOut()).resolves.toBeUndefined();

    expect(document.cookie).not.toContain('sb-example-auth-token');
    expect(document.cookie).toContain('unrelated-cookie=keep-me');
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().error).toMatch(/could not be revoked/i);
  });
});
