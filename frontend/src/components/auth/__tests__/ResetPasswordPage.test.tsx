import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { act, render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import ResetPasswordPage from '../../../../app/(auth)/reset-password/page';

type AuthChangeHandler = (event: string) => void;

const handlers: AuthChangeHandler[] = [];
const mockGetSession = vi.fn();
const mockUnsubscribe = vi.fn();

const emit = (event: string) => handlers.forEach((handler) => handler(event));

vi.mock('@/lib/supabase/client', () => ({
  createClient: () => ({
    auth: {
      onAuthStateChange: (handler: AuthChangeHandler) => {
        handlers.push(handler);
        return { data: { subscription: { unsubscribe: mockUnsubscribe } } };
      },
      getSession: mockGetSession,
      updateUser: vi.fn().mockResolvedValue({ error: null }),
    },
  }),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('next/link', () => ({
  __esModule: true,
  default: ({ children, href }: { children: ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const RECOVERY_SESSION = { data: { session: { access_token: 'recovery' } } };
const NO_SESSION = { data: { session: null } };

describe('ResetPasswordPage recovery-session gating', () => {
  beforeEach(() => {
    handlers.length = 0;
    vi.clearAllMocks();
    mockGetSession.mockResolvedValue(NO_SESSION);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('does not declare the link expired while the recovery session is still resolving', async () => {
    vi.useFakeTimers();
    let resolveSession: (value: unknown) => void = () => undefined;
    mockGetSession.mockReturnValue(
      new Promise((resolve) => {
        resolveSession = resolve;
      })
    );

    render(<ResetPasswordPage />);

    // Well past the old fixed 5s "expired" deadline.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(9000);
    });
    expect(
      screen.queryByText(/this link has expired/i)
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/verifying your recovery session/i)
    ).toBeInTheDocument();

    await act(async () => {
      resolveSession(RECOVERY_SESSION);
      await Promise.resolve();
    });

    expect(screen.getByText(/set a new password/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/this link has expired/i)
    ).not.toBeInTheDocument();
  });

  it('lets a late PASSWORD_RECOVERY event replace the expired view', async () => {
    mockGetSession.mockResolvedValue(NO_SESSION);

    render(<ResetPasswordPage />);

    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText(/this link has expired/i)).toBeInTheDocument();

    await act(async () => {
      emit('PASSWORD_RECOVERY');
    });

    expect(screen.getByText(/set a new password/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/this link has expired/i)
    ).not.toBeInTheDocument();
  });

  it('reports an expired link when no recovery session is established', async () => {
    render(<ResetPasswordPage />);

    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByText(/this link has expired/i)).toBeInTheDocument();
    expect(screen.queryByText(/set a new password/i)).not.toBeInTheDocument();
  });

  it('opens the form immediately when the recovery session is already available', async () => {
    mockGetSession.mockResolvedValue(RECOVERY_SESSION);

    render(<ResetPasswordPage />);

    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByText(/set a new password/i)).toBeInTheDocument();
  });
});
