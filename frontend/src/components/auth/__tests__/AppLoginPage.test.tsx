import { Mock, beforeEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import LoginPage from '../../../../app/(auth)/login/page';
import { downloadStoredNousCliAuth } from '@/services/nousCliAuth';

const mockLogin = vi.fn();
const mockPush = vi.fn();
let mockSearchParams = new URLSearchParams();

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

describe('App login page', () => {
  beforeEach(() => {
    mockLogin.mockReset();
    mockPush.mockReset();
    mockSearchParams = new URLSearchParams();
    mockedAuth.isAuthenticated = false;
    mockedAuth.isLoading = false;
    (downloadStoredNousCliAuth as Mock).mockReset();
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation(() => ({
        matches: false,
        media: '(prefers-reduced-motion: reduce)',
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  it('downloads NOUS CLI auth when selected before sign in', async () => {
    mockLogin.mockResolvedValue(undefined);

    render(<LoginPage />);

    const checkbox = await screen.findByLabelText(
      /download nous cli auth after sign in/i
    );
    fireEvent.change(screen.getByTestId('email-input'), {
      target: { value: 'admin@multimodal-rag.com' },
    });
    fireEvent.change(screen.getByTestId('password-input'), {
      target: { value: 'secret-password' },
    });
    fireEvent.click(checkbox);
    fireEvent.click(screen.getByTestId('login-button'));

    await waitFor(() =>
      expect(mockLogin).toHaveBeenCalledWith(
        'admin@multimodal-rag.com',
        'secret-password'
      )
    );
    expect(downloadStoredNousCliAuth).toHaveBeenCalledTimes(1);
  });

  it('does not download NOUS CLI auth unless selected', async () => {
    mockLogin.mockResolvedValue(undefined);

    render(<LoginPage />);

    await screen.findByTestId('email-input');
    fireEvent.change(screen.getByTestId('email-input'), {
      target: { value: 'admin@multimodal-rag.com' },
    });
    fireEvent.change(screen.getByTestId('password-input'), {
      target: { value: 'secret-password' },
    });
    fireEvent.click(screen.getByTestId('login-button'));

    await waitFor(() =>
      expect(mockLogin).toHaveBeenCalledWith(
        'admin@multimodal-rag.com',
        'secret-password'
      )
    );
    expect(downloadStoredNousCliAuth).not.toHaveBeenCalled();
  });

  it('redirects to the requested next path after login', async () => {
    mockLogin.mockResolvedValue(undefined);
    mockSearchParams = new URLSearchParams(
      'next=%2Fcli-auth%3Fsession_id%3Dsession-1%26code%3DABCD-1234'
    );

    render(<LoginPage />);

    await screen.findByTestId('email-input');
    fireEvent.change(screen.getByTestId('email-input'), {
      target: { value: 'admin@multimodal-rag.com' },
    });
    fireEvent.change(screen.getByTestId('password-input'), {
      target: { value: 'secret-password' },
    });
    fireEvent.click(screen.getByTestId('login-button'));

    await waitFor(() =>
      expect(mockLogin).toHaveBeenCalledWith(
        'admin@multimodal-rag.com',
        'secret-password'
      )
    );
    expect(mockPush).toHaveBeenCalledWith('/cli-auth?session_id=session-1&code=ABCD-1234');
  });

  it.each([
    ['//evil.com', '/dashboard'],
    ['http://evil.com', '/dashboard'],
    ['', '/dashboard'],
  ])(
    'blocks open redirect for next=%s and falls back to /dashboard',
    async (maliciousNext, expectedPath) => {
      mockLogin.mockResolvedValue(undefined);
      mockSearchParams = new URLSearchParams(`next=${encodeURIComponent(maliciousNext)}`);

      render(<LoginPage />);

      await screen.findByTestId('email-input');
      fireEvent.change(screen.getByTestId('email-input'), {
        target: { value: 'admin@multimodal-rag.com' },
      });
      fireEvent.change(screen.getByTestId('password-input'), {
        target: { value: 'secret-password' },
      });
      fireEvent.click(screen.getByTestId('login-button'));

      await waitFor(() => expect(mockLogin).toHaveBeenCalled());
      expect(mockPush).toHaveBeenCalledWith(expectedPath);
    }
  );
});
