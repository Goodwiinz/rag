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

    let useAuthStore: typeof import('@/stores/authStore').useAuthStore;
    await vi.isolateModulesAsync(async () => {
      ({ useAuthStore } =
        await vi.importActual<typeof import('@/stores/authStore')>(
          '@/stores/authStore'
        ));
    });

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
});
