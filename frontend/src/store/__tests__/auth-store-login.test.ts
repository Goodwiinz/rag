describe('useAuthStore signIn configuration handling', () => {
  const originalSupabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const originalSupabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  beforeEach(() => {
    jest.resetModules();
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  });

  afterEach(() => {
    jest.resetModules();

    if (originalSupabaseUrl === undefined) {
      delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    } else {
      process.env.NEXT_PUBLIC_SUPABASE_URL = originalSupabaseUrl;
    }

    if (originalSupabaseAnonKey === undefined) {
      delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    } else {
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = originalSupabaseAnonKey;
    }
  });

  it('does not throw while importing the auth store when browser Supabase config is missing', () => {
    expect(() => {
      jest.isolateModules(() => {
        require('@/store/authStore');
      });
    }).not.toThrow();
  });

  it('rejects signIn with a build-time config error when browser Supabase config is missing', async () => {
    let useAuthStore: typeof import('@/store/authStore').useAuthStore;

    jest.isolateModules(() => {
      ({ useAuthStore } = require('@/store/authStore'));
    });

    await expect(
      useAuthStore.getState().signIn('admin@test.com', 'wrong-password')
    ).rejects.toThrow(/build time/i);

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.error).toMatch(/build time/i);
  });
});
