'use client';

import React, { useState, useEffect, useCallback, createContext, useContext, ReactNode } from 'react';
import { AuthState, User, LoginRequest, RegisterRequest } from '@/types';
import { apiClient, setAuth, clearAuth } from '@/services/api';
import { useAuthStore } from '@/stores/authStore';
import { cleanupWebSocket } from '@/services/websocket';

interface AuthContextType extends AuthState {
  login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
  register: (userData: RegisterRequest) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  handleAuthError: () => void;
  rememberMe: boolean;
  sessionTimeRemaining: () => { accessRemaining: number; refreshRemaining: number };
}

const AuthContext = createContext<AuthContextType | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const {
    user,
    token,
    isAuthenticated,
    isLoading,
    error,
    rememberMe,
    login: storeLogin,
    register: storeRegister,
    logout: storeLogout,
    refreshToken,
    initializeFromStorage,
    getSessionTimeRemaining,
  } = useAuthStore();

  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: true,
    error: null,
  });

  // Clear stored auth data
  const clearStoredAuth = useCallback(() => {
    try {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user_data');
      clearAuth();
    } catch (error) {
      console.error('Error clearing auth data:', error);
    }
  }, []);

  // Logout function (defined first to avoid circular dependency)
  const logout = useCallback(() => {
    cleanupWebSocket();
    storeLogout();
  }, [storeLogout]);

  // Handle authentication errors (401 responses)
  const handleAuthError = useCallback(() => {
    console.warn('Authentication error detected, logging out...');
    cleanupWebSocket();
    storeLogout();
  }, [storeLogout]);

  // Store auth data in localStorage
  const storeAuthData = useCallback((token: string, user: User) => {
    try {
      localStorage.setItem('access_token', token);
      localStorage.setItem('user_data', JSON.stringify(user));
      setAuth(token, user.organization_id);
    } catch (error) {
      console.error('Error storing auth data:', error);
    }
  }, []);

  // Sync auth state with store
  useEffect(() => {
    setAuthState({
      user,
      token,
      isAuthenticated,
      isLoading,
      error,
    });

    // Keep the old API client in sync for now
    if (token && user?.organization_id) {
      setAuth(token, user.organization_id);
    } else {
      clearAuth();
    }
  }, [user, token, isAuthenticated, isLoading, error, setAuth, clearAuth]);

  // Initialize auth store from localStorage on mount
  useEffect(() => {
    initializeFromStorage();
  }, [initializeFromStorage]);

  // Keep localStorage in sync with store (for compatibility with old system)
  useEffect(() => {
    try {
      if (token && user) {
        localStorage.setItem('access_token', token);
        localStorage.setItem('user_data', JSON.stringify(user));
        setAuth(token, user.organization_id);
      } else {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_data');
        clearAuth();
      }
    } catch (error) {
      console.error('Error syncing auth data to localStorage:', error);
    }
  }, [token, user, setAuth, clearAuth]);

  // Login function with optional rememberMe for 30-day sessions
  const login = useCallback(async (email: string, password: string, rememberMe: boolean = false) => {
    await storeLogin(email, password, rememberMe);
  }, [storeLogin]);

  // Register function
  const register = useCallback(async (userData: RegisterRequest) => {
    await storeRegister(userData);
  }, [storeRegister]);

  // Refresh token function
  const refreshTokenCallback = useCallback(async () => {
    try {
      await refreshToken();
    } catch (error) {
      console.error('Token refresh failed:', error);
      cleanupWebSocket();
      storeLogout();
    }
  }, [refreshToken, storeLogout]);

  const contextValue: AuthContextType = {
    ...authState,
    login,
    register,
    logout,
    refreshToken: refreshTokenCallback,
    handleAuthError,
    rememberMe,
    sessionTimeRemaining: getSessionTimeRemaining,
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