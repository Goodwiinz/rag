import { createClient as createSupabaseBrowserClient } from '@/lib/supabase/client';
import { apiClient } from '@/services/apiClient';
import { Organization, RegisterResult, User } from '@/types';
import type { SupabaseClient } from '@supabase/supabase-js';
import { create } from 'zustand';

interface SwitchOrganizationResponse {
  organization: Organization;
}

interface ProfileResponse {
  user: User;
  organization?: Organization;
}

interface AuthState {
  // State
  user: User | null;
  organization: Organization | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  pendingEmailConfirmation: boolean;

  // Actions
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (userData: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
    organization_name?: string;
  }) => Promise<RegisterResult>;
  signOut: () => void;
  resetPassword: (email: string) => Promise<void>;
  fetchProfile: () => Promise<void>;
  updateUser: (user: Partial<User>) => void;
  switchOrganization: (organizationId: string) => Promise<void>;
  clearError: () => void;
  setLoading: (loading: boolean) => void;
  initialize: () => Promise<void>;
}

let authStateListenerRegistered = false;

function getSupabaseClient(): SupabaseClient {
  const supabase = createSupabaseBrowserClient();

  if (!authStateListenerRegistered) {
    supabase.auth.onAuthStateChange((event, session) => {
      if ((event === 'SIGNED_IN' || event === 'TOKEN_REFRESHED') && session) {
        const currentUser = useAuthStore.getState().user;
        if (!currentUser) {
          void useAuthStore.getState().fetchProfile();
        }
      }

      if (event === 'SIGNED_OUT') {
        useAuthStore.setState({
          user: null,
          organization: null,
          isAuthenticated: false,
          error: null,
          pendingEmailConfirmation: false,
        });
      }
    });

    authStateListenerRegistered = true;
  }

  return supabase;
}

export const useAuthStore = create<AuthState>()((set, get) => ({
  // Initial state
  user: null,
  organization: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,
  pendingEmailConfirmation: false,

  signIn: async (email: string, password: string) => {
    set({ isLoading: true, error: null });

    try {
      const supabase = getSupabaseClient();
      const { data, error: supabaseError } =
        await supabase.auth.signInWithPassword({
          email,
          password,
        });

      if (supabaseError) {
        throw new Error(supabaseError.message);
      }

      // Use the session from signIn directly — getSession() may return null
      // before the SSR cookie is established
      if (data.session) {
        const accessToken = data.session.access_token;
        const profileData = await apiClient.get<ProfileResponse>('/auth/me', {
          headers: { Authorization: `Bearer ${accessToken}` },
        });

        set({
          user: profileData.user,
          organization: profileData.organization ?? null,
          isAuthenticated: true,
          isLoading: false,
          pendingEmailConfirmation: false,
        });
      } else {
        set({ isLoading: false });
      }
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

  signUp: async (userData: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
    organization_name?: string;
  }) => {
    set({ isLoading: true, error: null, pendingEmailConfirmation: false });

    try {
      const supabase = getSupabaseClient();
      const emailRedirectTo = new URL('/auth/callback', window.location.origin);
      emailRedirectTo.searchParams.set('next', '/verify-email');

      const { data: supabaseData, error: supabaseError } =
        await supabase.auth.signUp({
          email: userData.email,
          password: userData.password,
          options: {
            data: {
              first_name: userData.first_name,
              last_name: userData.last_name,
              organization_name: userData.organization_name,
            },
            emailRedirectTo: emailRedirectTo.toString(),
          },
        });

      if (supabaseError) {
        throw new Error(supabaseError.message);
      }

      if (supabaseData.session) {
        await get().fetchProfile();
        return { requiresEmailConfirmation: false };
      }

      // No session = email confirmation required
      set({ isLoading: false, pendingEmailConfirmation: true });
      return { requiresEmailConfirmation: true };
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Registration failed',
        isLoading: false,
      });
      throw error;
    }
  },

  signOut: () => {
    try {
      getSupabaseClient()
        .auth.signOut()
        .catch(() => {});
    } catch {
      // If browser auth was never configured correctly, still clear local state.
    }

    set({
      user: null,
      organization: null,
      isAuthenticated: false,
      error: null,
      pendingEmailConfirmation: false,
    });
  },

  resetPassword: async (email: string) => {
    set({ isLoading: true, error: null });

    try {
      const supabase = getSupabaseClient();
      const { error: supabaseError } =
        await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: window.location.origin + '/reset-password',
        });

      if (supabaseError) {
        throw new Error(supabaseError.message);
      }

      set({ isLoading: false });
    } catch (error) {
      set({
        error:
          error instanceof Error ? error.message : 'Failed to send reset email',
        isLoading: false,
      });
      throw error;
    }
  },

  fetchProfile: async () => {
    try {
      const supabase = getSupabaseClient();
      const { data: sessionData, error: sessionError } =
        await supabase.auth.getSession();

      if (sessionError || !sessionData.session) {
        set({
          user: null,
          organization: null,
          isAuthenticated: false,
          isLoading: false,
        });
        return;
      }

      const accessToken = sessionData.session.access_token;

      const profileData = await apiClient.get<ProfileResponse>('/auth/me', {
        headers: { Authorization: `Bearer ${accessToken}` },
      });

      set({
        user: profileData.user,
        organization: profileData.organization ?? null,
        isAuthenticated: true,
        isLoading: false,
        pendingEmailConfirmation: false,
      });
    } catch (error) {
      set({
        user: null,
        organization: null,
        isAuthenticated: false,
        isLoading: false,
        error:
          error instanceof Error ? error.message : 'Failed to fetch profile',
      });
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
        { organizationId }
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

  initialize: async () => {
    try {
      const supabase = getSupabaseClient();
      const { data: sessionData, error: sessionError } =
        await supabase.auth.getSession();

      if (sessionError || !sessionData.session) {
        set({ isAuthenticated: false, isLoading: false });
        return;
      }

      await get().fetchProfile();
    } catch (error) {
      set({
        isAuthenticated: false,
        isLoading: false,
        error:
          error instanceof Error
            ? error.message
            : 'Failed to initialize authentication',
      });
    }
  },
}));
