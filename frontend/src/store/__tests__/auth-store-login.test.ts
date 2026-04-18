import { apiClient } from '@/services/apiClient';
import { useAuthStore } from '@/stores/authStore';

jest.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      signInWithPassword: jest.fn().mockResolvedValue({
        data: null,
        error: { message: 'Invalid login credentials' },
      }),
      signUp: jest.fn(),
      signOut: jest.fn(),
      refreshSession: jest.fn(),
      onAuthStateChange: jest.fn(() => ({
        data: { subscription: { unsubscribe: jest.fn() } },
      })),
    },
  },
}));

jest.mock('@/services/apiClient', () => ({
  apiClient: {
    post: jest.fn(),
  },
}));

const mockApiClient = apiClient as jest.Mocked<typeof apiClient>;

describe('useAuthStore login error handling', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    useAuthStore.getState().stopProactiveRefresh();
    useAuthStore.setState({
      user: null,
      organization: null,
      token: null,
      refreshTokenValue: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
      rememberMe: false,
      tokenExpiresAt: null,
      refreshExpiresAt: null,
    });
  });

  it('rejects the login promise when API authentication fails', async () => {
    mockApiClient.post.mockRejectedValue(new Error('Invalid credentials'));

    await expect(
      useAuthStore.getState().login('admin@test.com', 'wrong-password')
    ).rejects.toThrow('Invalid credentials');

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.error).toBe('Invalid credentials');
  });
});
