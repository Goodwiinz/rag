import React from 'react';
import { AuthProvider } from '@/hooks';
import { AppRouter } from '@/router';
import '@/index.css';

/**
 * Main Application Component
 *
 * Provides the application structure with:
 * - Authentication context provider
 * - Routing system
 * - Global styles
 */
function App() {
  return (
    <AuthProvider>
      <AppRouter />
    </AuthProvider>
  );
}

export default App;