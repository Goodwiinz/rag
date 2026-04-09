'use client';

import React, {
  useEffect,
  createContext,
  useContext,
  useCallback,
  ReactNode,
} from 'react';
import { User, Organization, RegisterRequest } from '@/types';
import { useAuthStore } from '@/stores/authStore';

interface AuthContextType {
  user: User | null;
  organization: Organization | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  pendingEmailConfirmation: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (userData: RegisterRequest) => Promise<void>;
  signOut: () => void;
  resetPassword: (email: string) => Promise<void>;
  fetchProfile: () => Promise<void>;
  handleAuthError: () => void;
  // Legacy aliases for backward compatibility
  login: (email: string, password: string) => Promise<void>;
  register: (userData: RegisterRequest) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const store = useAuthStore();

  // Initialize auth state on mount
  useEffect(() => {
    store.initialize();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only run on mount
  }, []);

  const handleAuthError = useCallback(() => {
    store.signOut();
  }, [store]);

  const contextValue: AuthContextType = {
    user: store.user,
    organization: store.organization,
    isAuthenticated: store.isAuthenticated,
    isLoading: store.isLoading,
    error: store.error,
    pendingEmailConfirmation: store.pendingEmailConfirmation,
    signIn: store.signIn,
    signUp: store.signUp,
    signOut: store.signOut,
    resetPassword: store.resetPassword,
    fetchProfile: store.fetchProfile,
    handleAuthError,
    // Legacy aliases
    login: store.signIn,
    register: store.signUp,
    logout: store.signOut,
  };

  return React.createElement(
    AuthContext.Provider,
    { value: contextValue },
    children
  );
};

// Hook to use auth context
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export default useAuth;
