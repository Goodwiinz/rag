/**
 * Central test render utility — wraps components with all required providers.
 * Usage: import { render, screen } from '@/test/test-utils';
 */
import React, { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

function AllProviders({ children }: { children: React.ReactNode }) {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

function customRender(
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'> & { wrapper?: React.ComponentType }
) {
  const Wrapper = options?.wrapper ?? AllProviders;
  return {
    user: userEvent.setup(),
    ...render(ui, { wrapper: Wrapper, ...options }),
  };
}

// Re-export everything from testing-library
export * from '@testing-library/react';
export { customRender as render, createTestQueryClient, AllProviders };
