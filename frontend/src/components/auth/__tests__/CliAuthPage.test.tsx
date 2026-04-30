import { beforeEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { apiClient } from '@/services/apiClient';

import CliAuthPage from '../../../../app/(auth)/cli-auth/page';

const mockPush = vi.fn();

const mockedAuth = {
  isAuthenticated: true,
  isLoading: false,
};

const mockSearchParams = new URLSearchParams(
  'session_id=session-1&code=ABCD-1234'
);

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => mockedAuth,
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  useSearchParams: () => mockSearchParams,
}));

vi.mock('next/link', () => ({
  __esModule: true,
  default: ({
    children,
    href,
    ...props
  }: {
    children: ReactNode;
    href: string;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

describe('CliAuthPage', () => {
  beforeEach(() => {
    mockPush.mockReset();
    vi.restoreAllMocks();
    mockedAuth.isAuthenticated = true;
    mockedAuth.isLoading = false;
  });

  it('shows approve action for authenticated browser session', async () => {
    render(<CliAuthPage />);

    expect(
      await screen.findByRole('button', { name: /approve cli login/i })
    ).toBeInTheDocument();
  });

  it('approves the CLI login and shows the connected state', async () => {
    const postSpy = vi.spyOn(apiClient, 'post')
      .mockResolvedValue({ status: 'approved' } as never);

    render(<CliAuthPage />);

    fireEvent.click(
      await screen.findByRole('button', { name: /approve cli login/i })
    );

    await waitFor(() =>
      expect(postSpy).toHaveBeenCalledWith('/cli-auth/approve', {
        session_id: 'session-1',
        verification_code: 'ABCD-1234',
      })
    );
    expect(
      await screen.findByText(/cli connected, return to terminal/i)
    ).toBeInTheDocument();
  });
});
