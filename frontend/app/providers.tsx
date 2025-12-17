'use client';

import { AuthSyncProvider } from '@/components/auth/AuthSyncProvider';
import { AnalyticsProvider } from '@/components/analytics/AnalyticsProvider';
import { AuthProvider } from '@/hooks';
import { components } from '@/lib/tambo';
import { TamboProvider } from '@tambo-ai/react';
import React from 'react';
import { Toaster } from 'react-hot-toast';

interface ProvidersProps {
  children: React.ReactNode;
}

export const Providers: React.FC<ProvidersProps> = ({ children }) => {
  return (
    <AnalyticsProvider>
      <AuthProvider>
        <AuthSyncProvider>
          <TamboProvider
            apiKey={process.env.NEXT_PUBLIC_TAMBO_API_KEY ?? ''}
            components={components}
          >
            {children}
          </TamboProvider>
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
    </AnalyticsProvider>
  );
};