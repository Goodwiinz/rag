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
    });
    mockSignUp.mockResolvedValue({
      data: { session: null },
      error: null,
    });
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
});
