'use client';

// Note: AnalyticsProvider is temporarily disabled for TypeScript strict mode
// import { AnalyticsProvider } from '@/components/analytics/AnalyticsProvider';
import { AuthSyncProvider } from '@/components/auth/AuthSyncProvider';
import { AuthProvider } from '@/hooks';
import React from 'react';
import { Toaster } from 'react-hot-toast';

interface ProvidersProps {
  children: React.ReactNode;
}

export function Providers({ children }: ProvidersProps) {
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
}

export default Providers;