import React, { useEffect } from 'react';
import { useAuthStore } from '@/stores/authStore';

interface AuthSyncProviderProps {
  children: React.ReactNode;
}

/**
 * Component to synchronize useAuthStore with localStorage data
 * This ensures that the Zustand store stays in sync with the useAuth context
 */
export const AuthSyncProvider: React.FC<AuthSyncProviderProps> = ({
  children,
}) => {
  const { initializeFromStorage } = useAuthStore();

  useEffect(() => {
    // Initialize auth state from localStorage on component mount
    initializeFromStorage();
  }, [initializeFromStorage]);

  return <>{children}</>;
};

export default AuthSyncProvider;
