import React, { useEffect } from 'react';
import { useAuthStore } from '@/stores/authStore';

interface AuthSyncProviderProps {
  children: React.ReactNode;
}

/**
 * Component to synchronize useAuthStore with Supabase session data.
 * Note: The AuthProvider in useAuth.tsx already calls store.initialize() on mount,
 * so this component is kept for any additional mount points that need auth sync.
 */
export const AuthSyncProvider: React.FC<AuthSyncProviderProps> = ({
  children,
}) => {
  const initialize = useAuthStore((state) => state.initialize);

  useEffect(() => {
    // Initialize auth state from Supabase session on component mount
    initialize();
  }, [initialize]);

  return <>{children}</>;
};

export default AuthSyncProvider;
