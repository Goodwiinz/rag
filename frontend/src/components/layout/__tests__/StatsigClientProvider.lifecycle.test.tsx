import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';

const mockInitializeAsync = vi.fn().mockResolvedValue(undefined);
const mockUpdateUserAsync = vi.fn().mockResolvedValue(undefined);
const mockUseClientAsyncInit = vi.fn();

const mockClient = {
  initializeAsync: mockInitializeAsync,
  updateUserAsync: mockUpdateUserAsync,
  loadingStatus: 'Ready',
  $on: vi.fn(),
  off: vi.fn(),
  flush: vi.fn().mockResolvedValue(undefined),
};

vi.mock('@/hooks', () => ({
  useAuth: () => ({ user: null }),
}));

vi.mock('@statsig/session-replay', () => ({
  StatsigSessionReplayPlugin: vi.fn(),
}));

vi.mock('@statsig/web-analytics', () => ({
  StatsigAutoCapturePlugin: vi.fn(),
}));

vi.mock('@statsig/react-bindings', () => ({
  LogLevel: { Warn: 'Warn', Debug: 'Debug' },
  StatsigClient: vi.fn(() => mockClient),
  StatsigProvider: ({ children }: { children: ReactNode }) => (
    <div data-testid="statsig-provider">{children}</div>
  ),
  useClientAsyncInit: (...args: unknown[]) => {
    mockUseClientAsyncInit(...args);
    return { client: mockClient, isLoading: false };
  },
}));

describe('StatsigClientProvider lifecycle', () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_STATSIG_CLIENT_KEY = 'client-test-key';
    mockInitializeAsync.mockClear();
    mockUpdateUserAsync.mockClear();
    mockUseClientAsyncInit.mockClear();
  });

  it('does not use Statsig async initialization during render', async () => {
    const { StatsigClientProvider } =
      await import('../../../../app/statsig-provider');

    render(
      <StatsigClientProvider>
        <span>Application shell</span>
      </StatsigClientProvider>
    );

    expect(screen.getByText('Application shell')).toBeInTheDocument();
    expect(mockUseClientAsyncInit).not.toHaveBeenCalled();
  });
});
