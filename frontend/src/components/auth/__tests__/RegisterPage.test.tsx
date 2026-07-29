import { beforeEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import RegisterPage from '../../../../app/(auth)/register/page';

type RegisterResult = {
  requiresEmailConfirmation: boolean;
};

const mockPush = vi.fn();
const mockRegister = vi.fn<Promise<RegisterResult>, [unknown]>();

const mockClearPendingEmailConfirmation = vi.fn();

const mockedAuth = {
  register: mockRegister,
  isAuthenticated: false,
  isLoading: false,
  pendingEmailConfirmation: false,
  pendingConfirmationEmail: null as string | null,
  pendingSignupPossiblyExisting: false,
  clearPendingEmailConfirmation: mockClearPendingEmailConfirmation,
};

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => mockedAuth,
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

describe('RegisterPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedAuth.pendingEmailConfirmation = false;
    mockedAuth.pendingConfirmationEmail = null;
    mockedAuth.pendingSignupPossiblyExisting = false;
  });

  it('does not redirect when registration requires email confirmation', async () => {
    mockRegister.mockImplementation(async () => {
      mockedAuth.pendingEmailConfirmation = true;
      return { requiresEmailConfirmation: true };
    });

    render(<RegisterPage />);

    fireEvent.change(await screen.findByLabelText(/first name/i), {
      target: { value: 'Ada' },
    });
    fireEvent.change(screen.getByLabelText(/last name/i), {
      target: { value: 'Lovelace' },
    });
    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: 'ada@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/organization/i), {
      target: { value: 'Analytical Engine' },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: 'SecurePass123!' },
    });
    fireEvent.change(screen.getByLabelText(/confirm password/i), {
      target: { value: 'SecurePass123!' },
    });

    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledTimes(1);
    });
    expect(mockPush).not.toHaveBeenCalled();
    expect(
      await screen.findByRole('heading', { name: /verify your identity/i })
    ).toBeInTheDocument();
  });

  it('renders the pending screen with the store email after a remount', async () => {
    // Remount = pristine form state; only the store still knows the address.
    mockedAuth.pendingEmailConfirmation = true;
    mockedAuth.pendingConfirmationEmail = 'ada@example.com';

    render(<RegisterPage />);

    expect(await screen.findByText('ada@example.com')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /resend verification/i })
    ).toBeEnabled();
  });

  it('clears the pending confirmation through the store action on reset', async () => {
    mockedAuth.pendingEmailConfirmation = true;
    mockedAuth.pendingConfirmationEmail = 'ada@example.com';

    render(<RegisterPage />);

    fireEvent.click(
      await screen.findByRole('button', { name: /wrong email\? try again/i })
    );

    expect(mockClearPendingEmailConfirmation).toHaveBeenCalledTimes(1);
  });

  it('shows neutral existing-account guidance when the signup may hit a known address', async () => {
    mockedAuth.pendingEmailConfirmation = true;
    mockedAuth.pendingConfirmationEmail = 'ada@example.com';
    mockedAuth.pendingSignupPossiblyExisting = true;

    render(<RegisterPage />);

    expect(
      await screen.findByRole('link', { name: /sign in/i })
    ).toHaveAttribute('href', '/login');
    expect(
      screen.queryByRole('button', { name: /resend verification/i })
    ).not.toBeInTheDocument();
  });
});
