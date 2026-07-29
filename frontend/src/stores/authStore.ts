import { createClient as createSupabaseBrowserClient } from '@/lib/supabase/client';
import { api } from '@/services/api-client';
import { clearWorkspaceServiceCache } from '@/services/workspaceService';
import { Organization, RegisterResult, User } from '@/types';
import type { SupabaseClient } from '@supabase/supabase-js';
import { create } from 'zustand';

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
  signOut: () => Promise<void>;
  resetPassword: (email: string) => Promise<void>;
  fetchProfile: () => Promise<void>;
  updateUser: (user: Partial<User>) => void;
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
        clearWorkspaceServiceCache();
        // Drop the cached bearer token so the shared APIClient singleton can't
        // keep sending the signed-out user's JWT.
        api.clearAuth();
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
        const profileData = await api.get<ProfileResponse>('/auth/me', {
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

  signOut: async () => {
    clearWorkspaceServiceCache();
    // Clear the shared APIClient token immediately so no in-flight or
    // subsequent request can carry the old JWT, even if the network call
    // below fails.
    api.clearAuth();

    // Always clear local state first so the UI reflects signed-out
    // immediately regardless of the network outcome.
    set({
      user: null,
      organization: null,
      isAuthenticated: false,
      error: null,
      pendingEmailConfirmation: false,
    });

    try {
      const { error } = (await getSupabaseClient().auth.signOut()) ?? {};
      if (error) throw error;
    } catch (error) {
      // Surface the failure: the server-side token may NOT be revoked, so the
      // caller can decide whether to retry / warn rather than assume a clean
      // logout. Local state is already cleared above.
      const message =
        error instanceof Error ? error.message : 'Sign out failed';
      set({ error: message });
      throw error instanceof Error ? error : new Error(message);
    }
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
      // SECURITY (audit #7): gate on getUser(), which verifies the JWT with
      // Supabase, rather than getSession(), which only reads the (forgeable)
      // cookie — a forged session cookie must not make the app look
      // authenticated. getSession() is then used solely to read the token to
      // forward to /auth/me (the backend re-validates it).
      const {
        data: { user },
        error: userError,
      } = await supabase.auth.getUser();

      if (userError || !user) {
        set({
          user: null,
          organization: null,
          isAuthenticated: false,
          isLoading: false,
        });
        return;
      }

      const {
        data: { session },
      } = await supabase.auth.getSession();
      const accessToken = session?.access_token;

      if (!accessToken) {
        set({
          user: null,
          organization: null,
          isAuthenticated: false,
          isLoading: false,
        });
        return;
      }

      const profileData = await api.get<ProfileResponse>('/auth/me', {
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

  clearError: () => set({ error: null }),
  setLoading: (loading: boolean) => set({ isLoading: loading }),

  initialize: async () => {
    try {
      const supabase = getSupabaseClient();
      // SECURITY (audit #7): verify the JWT with getUser() before treating the
      // app as authenticated; getSession() alone trusts the cookie.
      const {
        data: { user },
        error: userError,
      } = await supabase.auth.getUser();

      if (userError || !user) {
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
