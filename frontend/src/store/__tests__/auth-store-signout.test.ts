describe('useAuthStore signOut', () => {
  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
  });

  it('clears workspace-scoped caches when signing out', () => {
    const mockBrowserSignOut = jest.fn().mockResolvedValue(undefined);
    const mockClearWorkspaceServiceCache = jest.fn();

    jest.doMock('@/lib/supabase/client', () => ({
      createClient: () => ({
        auth: {
          onAuthStateChange: jest.fn(),
          signOut: mockBrowserSignOut,
        },
      }),
    }));

    jest.doMock('@/services/workspaceService', () => ({
      clearWorkspaceServiceCache: mockClearWorkspaceServiceCache,
    }));

    let useAuthStore: typeof import('@/stores/authStore').useAuthStore;
    jest.isolateModules(() => {
      ({ useAuthStore } = require('@/stores/authStore'));
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
