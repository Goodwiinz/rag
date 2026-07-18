import type { QueryClient } from '@tanstack/react-query';

// Registry handle for the app's QueryClient so non-React modules (Zustand
// stores) can invalidate Query caches — the dual-cache reconciliation
// contract in docs/engineering/frontend.md ("Legacy server-state stores").
// Registered once by app/providers.tsx; null before mount and in unit tests
// that don't register one, so callers must optional-chain.
let appQueryClient: QueryClient | null = null;

export function setAppQueryClient(client: QueryClient): void {
  appQueryClient = client;
}

export function getAppQueryClient(): QueryClient | null {
  return appQueryClient;
}
