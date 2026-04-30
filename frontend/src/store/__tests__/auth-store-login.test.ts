import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
describe('useAuthStore signIn configuration handling', () => {
  const originalSupabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const originalSupabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  beforeEach(() => {
    vi.resetModules();
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  });

  afterEach(() => {
    vi.resetModules();

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

  it('does not throw while importing the auth store when browser Supabase config is missing', async () => {
    await expect(
      vi.isolateModulesAsync(async () => {
        await vi.importActual<typeof import('@/stores/authStore')>(
          '@/stores/authStore'
        );
      })
    ).resolves.not.toThrow();
  });

  it('rejects signIn with a build-time config error when browser Supabase config is missing', async () => {
    let useAuthStore: typeof import('@/stores/authStore').useAuthStore;

    await vi.isolateModulesAsync(async () => {
      ({ useAuthStore } =
        await vi.importActual<typeof import('@/stores/authStore')>(
          '@/stores/authStore'
        ));
    });

    await expect(
      useAuthStore.getState().signIn('admin@test.com', 'wrong-password')
    ).rejects.toThrow(/build time/i);

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.error).toMatch(/build time/i);
  });
});
