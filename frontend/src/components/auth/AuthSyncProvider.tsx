import React, { useEffect } from 'react';
import { useAuthStore } from '@/stores/authStore';

interface AuthSyncProviderProps {
  children: React.ReactNode;
}

/**
 * Component to synchronize useAuthStore with localStorage data
 * This ensures that the Zustand store stays in sync with the useAuth context
 */
export const AuthSyncProvider: React.FC<AuthSyncProviderProps> = ({ children }) => {
  const { initializeFromStorage, isAuthenticated, user, token } = useAuthStore();

  useEffect(() => {
    // Initialize auth state from localStorage on component mount
    initializeFromStorage();
  }, [initializeFromStorage]);

  // Debug logging to track synchronization
  useEffect(() => {
    console.log('🔄 AuthSyncProvider: Auth state synchronized', {
      isAuthenticated,
      hasUser: !!user,
      hasToken: !!token,
      userId: user?.id,
      userEmail: user?.email,
    });
  }, [isAuthenticated, user, token]);

  return <>{children}</>;
};

export default AuthSyncProvider;