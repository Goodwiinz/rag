const mockSignUp = jest.fn();

jest.mock('@/lib/supabase/client', () => ({
  createClient: () => ({
    auth: {
      signInWithPassword: jest.fn(),
      signUp: (...args: unknown[]) => mockSignUp(...args),
      signOut: jest.fn(),
      resetPasswordForEmail: jest.fn(),
      getSession: jest.fn().mockResolvedValue({
        data: { session: null },
        error: null,
      }),
      onAuthStateChange: jest.fn(() => ({
        data: { subscription: { unsubscribe: jest.fn() } },
      })),
    },
  }),
}));

jest.mock('@/services/apiClient', () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
  },
}));

import { useAuthStore } from '@/store/authStore';

describe('useAuthStore signUp', () => {
  beforeEach(() => {
    jest.clearAllMocks();
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
