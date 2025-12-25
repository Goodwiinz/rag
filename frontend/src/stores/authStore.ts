import { apiClient } from '@/services/apiClient';
import { Organization, User } from '@/types';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// API Response Types
interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
  organization?: Organization;
}

interface RefreshResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user?: User;
}

interface SwitchOrganizationResponse {
  organization: Organization;
}

interface AuthState {
  // State
  user: User | null;
  organization: Organization | null;
  token: string | null;
  refreshTokenValue: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  initializeFromStorage: () => void;
  login: (email: string, password: string) => Promise<void>;
  register: (userData: { email: string; password: string; full_name?: string }) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  updateUser: (user: Partial<User>) => void;
  switchOrganization: (organizationId: string) => Promise<void>;
  clearError: () => void;
  setLoading: (loading: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // Initial state
      user: null,
      organization: null,
      token: null,
      refreshTokenValue: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      // Initialize auth state from localStorage (for synchronization with useAuth)
      initializeFromStorage: () => {
        console.log('🔄 AuthStore: Initializing from localStorage');

        try {
          const token = localStorage.getItem('access_token');
          const storedRefreshToken = localStorage.getItem('refresh_token');
          const userData = localStorage.getItem('user_data');

          if (token && userData) {
            const user = JSON.parse(userData);
            console.log('🔄 AuthStore: Found auth data in localStorage', {
              hasToken: !!token,
              hasUser: !!user,
              userId: user.id,
              orgId: user.organization_id
            });

            // Create organization object from user data
            const organization = user.organization_id ? {
              id: user.organization_id,
              name: user.organization_name || 'Default Organization',
              plan: 'free' as const,
              storage_limit: 1000000000, // 1GB default
              member_count: 1,
              created_at: user.created_at || new Date().toISOString(),
            } : null;

            set({
              user,
              organization,
              token,
              refreshTokenValue: storedRefreshToken || null,
              isAuthenticated: true,
              isLoading: false,
              error: null,
            });

            console.log('✅ AuthStore: State synchronized with localStorage');
          } else {
            console.log('ℹ️ AuthStore: No auth data found in localStorage');
            set({ isLoading: false });
          }
        } catch (error) {
          console.error('❌ AuthStore: Failed to initialize from localStorage:', error);
          set({ isLoading: false, error: 'Failed to initialize auth state' });
        }
      },

      // Actions
      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });

        try {
          const data: LoginResponse = await apiClient.post('/auth/login', {
            email,
            password,
          });

          set({
            user: data.user,
            organization: data.organization,
            organization: data.organization,
            token: data.access_token,
            refreshTokenValue: data.refresh_token,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Login failed',
            isLoading: false,
          });
        }
      },

      register: async (userData: { email: string; password: string; full_name?: string }) => {
        set({ isLoading: true, error: null });

        try {
          const data: LoginResponse = await apiClient.post('/auth/register', userData);

          set({
            user: data.user,
            organization: data.organization,
            organization: data.organization,
            token: data.access_token,
            refreshTokenValue: data.refresh_token,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Registration failed',
            isLoading: false,
          });
        }
      },

      logout: () => {
        set({
          user: null,
          organization: null,
          token: null,
          refreshTokenValue: null,
          isAuthenticated: false,
          error: null,
        });
      },

      refreshToken: async () => {
        const { token } = get();
        if (!token) return;

        try {
          const data: RefreshResponse = await apiClient.post('/auth/refresh', {
            refresh_token: get().refreshTokenValue || token, // Use stored refresh token or fall back to access token
          });

          set({ 
            token: data.access_token,
            // Update refresh token if provided in response (rotation)
            ...(data.refresh_token && { refreshTokenValue: data.refresh_token })
          });
        } catch (error) {
          get().logout();
        }
      },

      updateUser: (userData: Partial<User>) => {
        const { user } = get();
        if (user) {
          set({ user: { ...user, ...userData } });
        }
      },

      switchOrganization: async (organizationId: string) => {
        set({ isLoading: true, error: null });

        try {
          const data: SwitchOrganizationResponse = await apiClient.post('/auth/switch-organization', {
            organizationId,
          });

          set({
            organization: data.organization,
            isLoading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to switch organization',
            isLoading: false,
          });
        }
      },

      clearError: () => set({ error: null }),
      setLoading: (loading: boolean) => set({ isLoading: loading }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        organization: state.organization,
        organization: state.organization,
        token: state.token,
        refreshTokenValue: state.refreshTokenValue,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);