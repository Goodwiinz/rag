import React from 'react';
import { AuthProvider } from '@/hooks';
import { QueryProvider } from '@/hooks/QueryProvider';
import { AppRouter } from '@/router';
import '@/index.css';

/**
 * Main Application Component
 *
 * Provides the application structure with:
 * - Authentication context provider
 * - React Query provider for server state management
 * - Routing system
 * - Global styles
 */
function App() {
  return (
    <AuthProvider>
      <QueryProvider>
        <AppRouter />
      </QueryProvider>
    </AuthProvider>
  );
}

export default App;