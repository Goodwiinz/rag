import { beforeEach, describe, expect, it, vi } from 'vitest';
import { APIErrorClass } from '@/types/api';

type AuthChangeHandler = (event: string, session: unknown) => void;

const SESSION = {
  access_token: 'access-token-1',
  user: { id: 'user-1' },
};

const PROFILE = {
  user: { id: 'user-1', email: 'ada@example.com' },
  organization: { id: 'org-1' },
};

interface Harness {
  useAuthStore: typeof import('@/stores/authStore').useAuthStore;
  apiGet: ReturnType<typeof vi.fn>;
  getUser: ReturnType<typeof vi.fn>;
  emit: (event: string, session: unknown) => void;
  signInWithPassword: ReturnType<typeof vi.fn>;
}

async function loadStore(
  options: { emitSignedInDuringSignIn?: boolean } = {}
): Promise<Harness> {
  const handlers: AuthChangeHandler[] = [];
  const emit = (event: string, session: unknown) =>
    handlers.forEach((handler) => handler(event, session));

  const apiGet = vi.fn().mockResolvedValue(PROFILE);
  const getUser = vi
    .fn()
    .mockResolvedValue({ data: { user: SESSION.user }, error: null });
  const signInWithPassword = vi.fn().mockImplementation(async () => {
    if (options.emitSignedInDuringSignIn) {
      // Mirrors supabase-js: SIGNED_IN is broadcast as part of the sign-in call.
      emit('SIGNED_IN', SESSION);
    }
    return { data: { session: SESSION }, error: null };
  });

  vi.doMock('@/lib/supabase/client', () => ({
    createClient: () => ({
      auth: {
        onAuthStateChange: (handler: AuthChangeHandler) => {
          handlers.push(handler);
          return { data: { subscription: { unsubscribe: vi.fn() } } };
        },
        signInWithPassword,
        signOut: vi.fn().mockResolvedValue({ error: null }),
        getUser,
        getSession: vi.fn().mockResolvedValue({ data: { session: SESSION } }),
      },
    }),
  }));

  vi.doMock('@/services/workspaceService', () => ({
    clearWorkspaceServiceCache: vi.fn(),
  }));

  vi.doMock('@/services/api-client', () => ({
    api: { get: apiGet, post: vi.fn(), clearAuth: vi.fn() },
  }));

  const { useAuthStore } =
    await vi.importActual<typeof import('@/stores/authStore')>(
      '@/stores/authStore'
    );

  return { useAuthStore, apiGet, getUser, emit, signInWithPassword };
}

describe('useAuthStore profile fetching', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it('does not issue a second /auth/me when SIGNED_IN fires during signIn', async () => {
    const { useAuthStore, apiGet } = await loadStore({
      emitSignedInDuringSignIn: true,
    });

    await useAuthStore.getState().signIn('ada@example.com', 'hunter2hunter2');
    // Let any listener-scheduled work run.
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(apiGet).toHaveBeenCalledTimes(1);
    expect(apiGet).toHaveBeenCalledWith('/auth/me', expect.anything());
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('collapses concurrent fetchProfile calls onto one /auth/me', async () => {
    const { useAuthStore, apiGet } = await loadStore();

    await Promise.all([
      useAuthStore.getState().fetchProfile(),
      useAuthStore.getState().fetchProfile(),
    ]);

    expect(apiGet).toHaveBeenCalledTimes(1);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('keeps an established session when the profile fetch fails transiently', async () => {
    const { useAuthStore, apiGet } = await loadStore();

    useAuthStore.setState({
      user: { id: 'user-1' } as never,
      organization: { id: 'org-1' } as never,
      isAuthenticated: true,
      isLoading: false,
      error: null,
    });

    apiGet.mockRejectedValueOnce(new Error('Network request failed'));
    await useAuthStore.getState().fetchProfile();

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.user).toEqual({ id: 'user-1' });
    expect(state.isLoading).toBe(false);
    expect(state.error).toBe('Network request failed');
  });

  it('still tears down the session when the token is rejected (401)', async () => {
    const { useAuthStore, apiGet } = await loadStore();

    useAuthStore.setState({
      user: { id: 'user-1' } as never,
      organization: { id: 'org-1' } as never,
      isAuthenticated: true,
      isLoading: false,
      error: null,
    });

    apiGet.mockRejectedValueOnce(
      new APIErrorClass({
        message: 'Invalid token',
        status_code: 401,
        type: 'auth_error',
      })
    );
    await useAuthStore.getState().fetchProfile();

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
    expect(state.error).toBe('Invalid token');
  });

  it('still tears down the session when Supabase cannot verify the user', async () => {
    const { useAuthStore, getUser } = await loadStore();

    useAuthStore.setState({
      user: { id: 'user-1' } as never,
      isAuthenticated: true,
      isLoading: false,
    });

    getUser.mockResolvedValueOnce({
      data: { user: null },
      error: { message: 'Auth session missing' },
    });
    await useAuthStore.getState().fetchProfile();

    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().user).toBeNull();
  });
});
