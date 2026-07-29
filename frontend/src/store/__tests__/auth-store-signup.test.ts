import { beforeEach, describe, expect, it, vi } from 'vitest';
const mockSignUp = vi.fn();

vi.mock('@/lib/supabase/client', () => ({
  createClient: () => ({
    auth: {
      signInWithPassword: vi.fn(),
      signUp: (...args: unknown[]) => mockSignUp(...args),
      signOut: vi.fn(),
      resetPasswordForEmail: vi.fn(),
      getSession: vi.fn().mockResolvedValue({
        data: { session: null },
        error: null,
      }),
      onAuthStateChange: vi.fn(() => ({
        data: { subscription: { unsubscribe: vi.fn() } },
      })),
    },
  }),
}));

vi.mock('@/services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import { useAuthStore } from '@/stores/authStore';
import type { RegisterResult } from '@/types';
import { AUTH_SERVICE_UNAVAILABLE } from '@/utils/supabaseAuthError';

describe('useAuthStore signUp', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      user: null,
      organization: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
      pendingEmailConfirmation: false,
      pendingConfirmationEmail: null,
      pendingSignupPossiblyExisting: false,
    });
    mockSignUp.mockResolvedValue({
      data: { session: null, user: { identities: [{ id: 'identity-1' }] } },
      error: null,
    });
  });

  const signUpAda = (): Promise<RegisterResult> =>
    useAuthStore.getState().signUp({
      email: 'ada@example.com',
      password: 'SecurePass123!',
      first_name: 'Ada',
      last_name: 'Lovelace',
      organization_name: 'Analytical Engine',
    });

  it('routes email confirmation through the callback endpoint', async () => {
    const result = await useAuthStore.getState().signUp({
      email: 'ada@example.com',
      password: 'SecurePass123!',
      first_name: 'Ada',
      last_name: 'Lovelace',
      organization_name: 'Analytical Engine',
    });

    expect(mockSignUp).toHaveBeenCalledWith({
      email: 'ada@example.com',
      password: 'SecurePass123!',
      options: {
        data: {
          first_name: 'Ada',
          last_name: 'Lovelace',
          organization_name: 'Analytical Engine',
        },
        emailRedirectTo:
          'http://localhost:3000/auth/callback?next=%2Fverify-email',
      },
    });
    expect(result).toEqual({ requiresEmailConfirmation: true });
  });

  it('stores the signup email alongside the pending flag', async () => {
    await signUpAda();

    expect(useAuthStore.getState().pendingEmailConfirmation).toBe(true);
    expect(useAuthStore.getState().pendingConfirmationEmail).toBe(
      'ada@example.com'
    );
  });

  it('clearPendingEmailConfirmation resets both flag and email', async () => {
    await signUpAda();

    useAuthStore.getState().clearPendingEmailConfirmation();

    expect(useAuthStore.getState()).toEqual(
      expect.objectContaining({
        pendingEmailConfirmation: false,
        pendingConfirmationEmail: null,
        pendingSignupPossiblyExisting: false,
      })
    );
  });

  it('flags an empty-identities user as possibly existing', async () => {
    // GoTrue's enumeration protection: already-registered address comes back
    // as a success with an obfuscated user carrying no identities.
    mockSignUp.mockResolvedValue({
      data: { session: null, user: { identities: [] } },
      error: null,
    });

    const result = await signUpAda();

    expect(result).toEqual({ requiresEmailConfirmation: true });
    expect(useAuthStore.getState().pendingEmailConfirmation).toBe(true);
    expect(useAuthStore.getState().pendingSignupPossiblyExisting).toBe(true);
  });

  it('treats a signup with populated identities as a normal pending confirmation', async () => {
    mockSignUp.mockResolvedValue({
      data: { session: null, user: { identities: [{ id: 'identity-1' }] } },
      error: null,
    });

    await signUpAda();

    expect(useAuthStore.getState().pendingEmailConfirmation).toBe(true);
    expect(useAuthStore.getState().pendingSignupPossiblyExisting).toBe(false);
  });

  it('treats a missing identities field as a normal pending confirmation', async () => {
    // Guards the `Array.isArray` predicate: absent must not read as empty.
    mockSignUp.mockResolvedValue({
      data: { session: null, user: {} },
      error: null,
    });

    await signUpAda();

    expect(useAuthStore.getState().pendingSignupPossiblyExisting).toBe(false);
  });

  it('never surfaces the "{}" message auth-js builds from a gateway 5xx', async () => {
    // auth-js stringifies the raw Response for 502/503/504/52x, and a Response
    // has no enumerable own properties — so `message` arrives as "{}".
    mockSignUp.mockResolvedValue({
      data: { session: null },
      error: {
        name: 'AuthRetryableFetchError',
        status: 503,
        message: '{}',
      },
    });

    await expect(
      useAuthStore.getState().signUp({
        email: 'ada@example.com',
        password: 'SecurePass123!',
        first_name: 'Ada',
        last_name: 'Lovelace',
      })
    ).rejects.toThrow(AUTH_SERVICE_UNAVAILABLE);

    expect(useAuthStore.getState().error).toBe(AUTH_SERVICE_UNAVAILABLE);
  });

  it('keeps a real GoTrue message', async () => {
    mockSignUp.mockResolvedValue({
      data: { session: null },
      error: {
        name: 'AuthApiError',
        status: 422,
        message: 'User already registered',
      },
    });

    await expect(
      useAuthStore.getState().signUp({
        email: 'ada@example.com',
        password: 'SecurePass123!',
        first_name: 'Ada',
        last_name: 'Lovelace',
      })
    ).rejects.toThrow('User already registered');

    expect(useAuthStore.getState().error).toBe('User already registered');
  });
});
