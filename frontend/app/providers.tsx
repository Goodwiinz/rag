'use client';

import React from 'react';
import { AuthProvider } from '@/hooks';
import { AuthSyncProvider } from '@/components/auth/AuthSyncProvider';
import { Toaster } from 'react-hot-toast';

interface ProvidersProps {
  children: React.ReactNode;
}

export const Providers: React.FC<ProvidersProps> = ({ children }) => {
  return (
    <AuthProvider>
      <AuthSyncProvider>
        {children}
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: 'hsl(var(--card))',
              color: 'hsl(var(--card-foreground))',
              border: '1px solid hsl(var(--border))',
            },
          }}
        />
      </AuthSyncProvider>
    </AuthProvider>
  );
};