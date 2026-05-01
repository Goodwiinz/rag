import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mock } from 'vitest';
import '@testing-library/jest-dom/vitest';
import type { ReactNode } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import LoginPage from '@/page-components/auth/LoginPage';
import { downloadStoredNousCliAuth } from '@/services/nousCliAuth';

const mockLogin = vi.fn();

const mockedAuth = {
  login: mockLogin,
  isAuthenticated: false,
  isLoading: false,
};

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => mockedAuth,
}));

vi.mock('@/services/nousCliAuth', () => ({
  downloadStoredNousCliAuth: vi.fn(),
}));

vi.mock('react-router-dom', () => ({
  Link: ({ children, to }: { children: ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
  Navigate: ({ to }: { to: string }) => <div data-testid="navigate">{to}</div>,
}));

describe('LoginPage', () => {
  beforeEach(() => {
    mockLogin.mockReset();
    mockedAuth.isAuthenticated = false;
    mockedAuth.isLoading = false;
    (downloadStoredNousCliAuth as Mock).mockReset();
  });

  it('downloads NOUS CLI auth when the option is selected', async () => {
    mockLogin.mockResolvedValue(undefined);

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText('Email address'), {
      target: { value: 'researcher@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'secret-password' },
    });
    fireEvent.click(
      screen.getByLabelText(/download nous cli auth after sign in/i)
    );
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() =>
      expect(mockLogin).toHaveBeenCalledWith(
        'researcher@example.com',
        'secret-password',
        false
      )
    );
    expect(downloadStoredNousCliAuth).toHaveBeenCalledTimes(1);
  });

  it('does not download NOUS CLI auth by default', async () => {
    mockLogin.mockResolvedValue(undefined);

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText('Email address'), {
      target: { value: 'researcher@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'secret-password' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() =>
      expect(mockLogin).toHaveBeenCalledWith(
        'researcher@example.com',
        'secret-password',
        false
      )
    );
    expect(downloadStoredNousCliAuth).not.toHaveBeenCalled();
  });
});
