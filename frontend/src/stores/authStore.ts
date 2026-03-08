import { supabase } from '@/lib/supabase';
import { apiClient } from '@/services/apiClient';
import { Organization, User } from '@/types';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Development-only logging to reduce production overhead
const debugLog =
  process.env.NODE_ENV === 'development'
    ? (...args: unknown[]) => console.log(...args)
    : () => {};

// API Response Types
interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  refresh_expires_in?: number; // Refresh token expiration in seconds
  remember_me: boolean; // Indicates if this is a 30-day session
  user: User;
  organization?: Organization;
}

interface RefreshResponse {
  access_token: string;
  refresh_token?: string; // New refresh token if rotated
  token_type: string;
  expires_in: number;
  refresh_expires_in?: number;
  remember_me?: boolean;
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
  // Session persistence state
  rememberMe: boolean; // If true, session persists for 30 days
  tokenExpiresAt: number | null; // Unix timestamp when access token expires
  refreshExpiresAt: number | null; // Unix timestamp when refresh token expires

  // Actions
  initializeFromStorage: () => void;
  login: (
    email: string,
    password: string,
    rememberMe?: boolean
  ) => Promise<void>;
  register: (userData: {
    email: string;
    password: string;
    full_name?: string;
  }) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  updateUser: (user: Partial<User>) => void;
  switchOrganization: (organizationId: string) => Promise<void>;
  clearError: () => void;
  setLoading: (loading: boolean) => void;
  // Session management
  startProactiveRefresh: () => void;
  stopProactiveRefresh: () => void;
  getSessionTimeRemaining: () => {
    accessRemaining: number;
    refreshRemaining: number;
  };
}

// Global refresh timer reference
let proactiveRefreshTimer: NodeJS.Timeout | null = null;

// Refresh token 5 minutes before expiration
const REFRESH_BUFFER_MS = 5 * 60 * 1000;

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
      // Session persistence state
      rememberMe: false,
      tokenExpiresAt: null,
      refreshExpiresAt: null,

      // Initialize auth state from localStorage (for synchronization with useAuth)
      initializeFromStorage: () => {
        debugLog('🔄 AuthStore: Initializing from localStorage');

        try {
          const token = localStorage.getItem('access_token');
          const storedRefreshToken = localStorage.getItem('refresh_token');
          const userData = localStorage.getItem('user_data');

          if (token && userData) {
            const user = JSON.parse(userData);
            debugLog('🔄 AuthStore: Found auth data in localStorage', {
              hasToken: !!token,
              hasUser: !!user,
              userId: user.id,
              orgId: user.organization_id,
            });

            // Create organization object from user data
            const organization = user.organization_id
              ? {
                  id: user.organization_id,
                  name: user.organization_name || 'Default Organization',
                  plan: 'free' as const,
                  storage_limit: 1000000000, // 1GB default
                  member_count: 1,
                  created_at: user.created_at || new Date().toISOString(),
                }
              : null;

            set({
              user,
              organization,
              token,
              refreshTokenValue: storedRefreshToken || null,
              isAuthenticated: true,
              isLoading: false,
              error: null,
            });

            // Start proactive token refresh if authenticated
            get().startProactiveRefresh();

            debugLog('✅ AuthStore: State synchronized with localStorage');
          } else {
            debugLog('ℹ️ AuthStore: No auth data found in localStorage');
            set({ isLoading: false });
          }
        } catch (error) {
          console.error(
            '❌ AuthStore: Failed to initialize from localStorage:',
            error
          );
          set({ isLoading: false, error: 'Failed to initialize auth state' });
        }
      },

      // Actions
      login: async (
        email: string,
        password: string,
        rememberMe: boolean = false
      ) => {
        set({ isLoading: true, error: null });

        try {
          // Try Supabase Auth first
          const { data: supabaseData, error: supabaseError } =
            await supabase.auth.signInWithPassword({
              email,
              password,
            });

          if (!supabaseError && supabaseData.session) {
            const session = supabaseData.session;

            // Fetch full user profile from backend using Supabase token
            const profileData = await apiClient.get<{
              user: User;
              organization?: Organization;
            }>('/auth/me', {
              headers: { Authorization: `Bearer ${session.access_token}` },
            });

            const now = Date.now();
            const tokenExpiresAt = session.expires_at
              ? session.expires_at * 1000
              : now + 3600000;
            const refreshExpiresAt =
              now +
              (rememberMe ? 30 * 24 * 60 * 60 * 1000 : 7 * 24 * 60 * 60 * 1000);

            set({
              user: profileData.user,
              organization: profileData.organization ?? null,
              token: session.access_token,
              refreshTokenValue: session.refresh_token,
              isAuthenticated: true,
              isLoading: false,
              rememberMe,
              tokenExpiresAt,
              refreshExpiresAt,
            });

            get().startProactiveRefresh();
            debugLog(
              `🔐 Supabase login successful - Session: ${rememberMe ? '30 days' : '7 days'}`
            );
            return;
          }

          // Fallback to custom auth
          debugLog(
            '⚠️ Supabase login failed, falling back to custom auth:',
            supabaseError?.message
          );
          const data: LoginResponse = await apiClient.post('/auth/login', {
            email,
            password,
            remember_me: rememberMe,
          });

          const now = Date.now();
          const tokenExpiresAt = now + data.expires_in * 1000;
          const refreshExpiresAt = data.refresh_expires_in
            ? now + data.refresh_expires_in * 1000
            : now +
              (rememberMe ? 30 * 24 * 60 * 60 * 1000 : 7 * 24 * 60 * 60 * 1000);

          set({
            user: data.user,
            organization: data.organization ?? null,
            token: data.access_token,
            refreshTokenValue: data.refresh_token,
            isAuthenticated: true,
            isLoading: false,
            rememberMe: data.remember_me || rememberMe,
            tokenExpiresAt,
            refreshExpiresAt,
          });

          get().startProactiveRefresh();
          debugLog(
            `🔐 Custom login successful - Session: ${rememberMe ? '30 days' : '7 days'}`
          );
        } catch (error) {
          const authError =
            error instanceof Error ? error : new Error('Login failed');
          set({
            error: authError.message,
            isLoading: false,
          });
          throw authError;
        }
      },

      register: async (userData: {
        email: string;
        password: string;
        full_name?: string;
      }) => {
        set({ isLoading: true, error: null });

        try {
          // Try Supabase Auth registration first
          const { data: supabaseData, error: supabaseError } =
            await supabase.auth.signUp({
              email: userData.email,
              password: userData.password,
              options: {
                data: {
                  full_name: userData.full_name,
                },
              },
            });

          if (!supabaseError && supabaseData.session) {
            const session = supabaseData.session;

            // Fetch user profile from backend
            const profileData = await apiClient.get<{
              user: User;
              organization?: Organization;
            }>('/auth/me', {
              headers: { Authorization: `Bearer ${session.access_token}` },
            });

            set({
              user: profileData.user,
              organization: profileData.organization ?? null,
              token: session.access_token,
              refreshTokenValue: session.refresh_token,
              isAuthenticated: true,
              isLoading: false,
            });
            return;
          }

          // Fallback to custom registration
          const data: LoginResponse = await apiClient.post(
            '/auth/register',
            userData
          );

          set({
            user: data.user,
            organization: data.organization ?? null,
            token: data.access_token,
            refreshTokenValue: data.refresh_token,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error) {
          set({
            error:
              error instanceof Error ? error.message : 'Registration failed',
            isLoading: false,
          });
        }
      },

      logout: () => {
        // Stop proactive refresh timer
        get().stopProactiveRefresh();

        // Sign out of Supabase (fire and forget)
        supabase.auth.signOut().catch(() => {});

        set({
          user: null,
          organization: null,
          token: null,
          refreshTokenValue: null,
          isAuthenticated: false,
          error: null,
          rememberMe: false,
          tokenExpiresAt: null,
          refreshExpiresAt: null,
        });

        debugLog('🔓 Logged out - Session cleared');
      },

      refreshToken: async () => {
        const { token, refreshTokenValue } = get();
        if (!token && !refreshTokenValue) return;

        try {
          // Try Supabase token refresh first
          const { data: supabaseData, error: supabaseError } =
            await supabase.auth.refreshSession();

          if (!supabaseError && supabaseData.session) {
            const session = supabaseData.session;
            const now = Date.now();
            const tokenExpiresAt = session.expires_at
              ? session.expires_at * 1000
              : now + 3600000;

            set({
              token: session.access_token,
              refreshTokenValue: session.refresh_token ?? null,
              tokenExpiresAt,
            });

            get().startProactiveRefresh();
            debugLog('🔄 Supabase token refreshed successfully');
            return;
          }

          // Fallback to custom token refresh
          const data: RefreshResponse = await apiClient.post('/auth/refresh', {
            refresh_token: refreshTokenValue || token,
          });

          const now = Date.now();
          const tokenExpiresAt = now + data.expires_in * 1000;

          const updates: Partial<AuthState> = {
            token: data.access_token,
            tokenExpiresAt,
          };

          if (data.refresh_token) {
            updates.refreshTokenValue = data.refresh_token;
            if (data.refresh_expires_in) {
              updates.refreshExpiresAt = now + data.refresh_expires_in * 1000;
            }
          }

          if (data.remember_me !== undefined) {
            updates.rememberMe = data.remember_me;
          }

          set(updates);
          get().startProactiveRefresh();
          debugLog('🔄 Custom token refreshed successfully');
        } catch (error) {
          console.error('❌ Token refresh failed:', error);
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
          const data: SwitchOrganizationResponse = await apiClient.post(
            '/auth/switch-organization',
            {
              organizationId,
            }
          );

          set({
            organization: data.organization,
            isLoading: false,
          });
        } catch (error) {
          set({
            error:
              error instanceof Error
                ? error.message
                : 'Failed to switch organization',
            isLoading: false,
          });
        }
      },

      clearError: () => set({ error: null }),
      setLoading: (loading: boolean) => set({ isLoading: loading }),

      // Session management - Proactive token refresh
      startProactiveRefresh: () => {
        const { tokenExpiresAt, isAuthenticated } = get();

        // Clear any existing timer
        if (proactiveRefreshTimer) {
          clearTimeout(proactiveRefreshTimer);
          proactiveRefreshTimer = null;
        }

        if (!isAuthenticated || !tokenExpiresAt) {
          return;
        }

        const now = Date.now();
        const timeUntilExpiry = tokenExpiresAt - now;
        const refreshIn = Math.max(timeUntilExpiry - REFRESH_BUFFER_MS, 60000); // At least 1 minute

        debugLog(
          `⏰ Proactive refresh scheduled in ${Math.round(refreshIn / 60000)} minutes`
        );

        proactiveRefreshTimer = setTimeout(async () => {
          debugLog('🔄 Proactive token refresh triggered');
          await get().refreshToken();
        }, refreshIn);
      },

      stopProactiveRefresh: () => {
        if (proactiveRefreshTimer) {
          clearTimeout(proactiveRefreshTimer);
          proactiveRefreshTimer = null;
          debugLog('⏹️ Proactive refresh stopped');
        }
      },

      getSessionTimeRemaining: () => {
        const { tokenExpiresAt, refreshExpiresAt } = get();
        const now = Date.now();

        return {
          accessRemaining: tokenExpiresAt
            ? Math.max(0, tokenExpiresAt - now)
            : 0,
          refreshRemaining: refreshExpiresAt
            ? Math.max(0, refreshExpiresAt - now)
            : 0,
        };
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        organization: state.organization,
        token: state.token,
        refreshTokenValue: state.refreshTokenValue,
        isAuthenticated: state.isAuthenticated,
        // Persist session state for 30-day sessions
        rememberMe: state.rememberMe,
        tokenExpiresAt: state.tokenExpiresAt,
        refreshExpiresAt: state.refreshExpiresAt,
      }),
      // Rehydrate session on app load
      onRehydrateStorage: () => (state) => {
        if (state?.isAuthenticated && state?.tokenExpiresAt) {
          // Check if refresh token is still valid
          const now = Date.now();
          if (state.refreshExpiresAt && state.refreshExpiresAt < now) {
            // Refresh token expired, logout
            debugLog('⚠️ Session expired during offline period');
            state.logout();
          } else if (state.tokenExpiresAt < now) {
            // Access token expired but refresh token valid - refresh immediately
            debugLog('🔄 Access token expired, refreshing...');
            state.refreshToken();
          } else {
            // Tokens still valid, start proactive refresh
            state.startProactiveRefresh();
          }
        }
      },
    }
  )
);

// Listen for Supabase auth state changes (token refresh, sign out)
supabase.auth.onAuthStateChange((event, session) => {
  if (event === 'TOKEN_REFRESHED' && session) {
    debugLog('🔄 Supabase token refreshed via onAuthStateChange');
    useAuthStore.setState({
      token: session.access_token,
      refreshTokenValue: session.refresh_token,
      tokenExpiresAt: session.expires_at ? session.expires_at * 1000 : null,
    });
  }
  if (event === 'SIGNED_OUT') {
    debugLog('🔓 Supabase signed out via onAuthStateChange');
    useAuthStore.setState({
      user: null,
      organization: null,
      token: null,
      refreshTokenValue: null,
      isAuthenticated: false,
      rememberMe: false,
      tokenExpiresAt: null,
      refreshExpiresAt: null,
    });
  }
});
