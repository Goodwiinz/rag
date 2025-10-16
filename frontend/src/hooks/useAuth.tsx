import React, { useState, useEffect, useCallback, createContext, useContext, ReactNode } from 'react';
import { AuthState, User, LoginRequest, RegisterRequest } from '@/types';
import { apiClient, setAuth, clearAuth } from '@/services/api';
import { cleanupWebSocket } from '@/services/websocket';

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (userData: RegisterRequest) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: true,
    error: null,
  });

  // Initialize auth state from localStorage
  useEffect(() => {
    const initializeAuth = () => {
      try {
        const token = localStorage.getItem('access_token');
        const userData = localStorage.getItem('user_data');

        if (token && userData) {
          const user = JSON.parse(userData);
          setAuthState({
            user,
            token,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
          setAuth(token, user.organization_id);
        } else {
          setAuthState(prev => ({ ...prev, isLoading: false }));
        }
      } catch (error) {
        console.error('Error initializing auth:', error);
        clearStoredAuth();
        setAuthState(prev => ({ ...prev, isLoading: false }));
      }
    };

    initializeAuth();
  }, []);

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
    clearStoredAuth();
    cleanupWebSocket();
    setAuthState({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
  }, [clearStoredAuth]);

  // Login function
  const login = useCallback(async (email: string, password: string) => {
    setAuthState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await apiClient.login({ email, password });
      const { access_token, user } = response;

      storeAuthData(access_token, user);

      setAuthState({
        user,
        token: access_token,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Login failed';
      setAuthState({
        user: null,
        token: null,
        isAuthenticated: false,
        isLoading: false,
        error: errorMessage,
      });
      throw new Error(errorMessage);
    }
  }, [storeAuthData]);

  // Register function
  const register = useCallback(async (userData: RegisterRequest) => {
    setAuthState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await apiClient.register(userData);
      const { access_token, user } = response;

      storeAuthData(access_token, user);

      setAuthState({
        user,
        token: access_token,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Registration failed';
      setAuthState({
        user: null,
        token: null,
        isAuthenticated: false,
        isLoading: false,
        error: errorMessage,
      });
      throw new Error(errorMessage);
    }
  }, [storeAuthData]);

  // Refresh token function
  const refreshToken = useCallback(async () => {
    try {
      const response = await apiClient.refreshToken();
      const { access_token, user } = response;

      storeAuthData(access_token, user);

      setAuthState(prev => ({
        ...prev,
        token: access_token,
        user,
        error: null,
      }));
    } catch (error) {
      console.error('Token refresh failed:', error);
      logout();
    }
  }, [storeAuthData, logout]);

  const contextValue: AuthContextType = {
    ...authState,
    login,
    register,
    logout,
    refreshToken,
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