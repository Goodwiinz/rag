import { beforeEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import PendingEmailConfirmation from '../PendingEmailConfirmation';

const mockResend = vi.fn();

vi.mock('@/lib/supabase/client', () => ({
  createClient: () => ({
    auth: {
      resend: (...args: unknown[]) => mockResend(...args),
    },
  }),
}));

describe('PendingEmailConfirmation', () => {
  beforeEach(() => {
    mockResend.mockReset();
    mockResend.mockResolvedValue({ data: {}, error: null });
  });

  it('calls supabase.auth.resend with the provided email', async () => {
    render(
      <PendingEmailConfirmation email="ada@example.com" onReset={vi.fn()} />
    );

    const resendButton = screen.getByRole('button', {
      name: /resend verification/i,
    });
    expect(resendButton).toBeEnabled();
    fireEvent.click(resendButton);

    await waitFor(() =>
      expect(mockResend).toHaveBeenCalledWith({
        type: 'signup',
        email: 'ada@example.com',
      })
    );
  });

  it('disables resend when no email is available', async () => {
    render(<PendingEmailConfirmation email="" onReset={vi.fn()} />);

    const resendButton = screen.getByRole('button', {
      name: /resend verification/i,
    });
    expect(resendButton).toBeDisabled();

    fireEvent.click(resendButton);

    expect(mockResend).not.toHaveBeenCalled();
  });

  it('shows neutral guidance with sign-in and reset-password links when possiblyExisting', () => {
    render(
      <PendingEmailConfirmation
        email="ada@example.com"
        possiblyExisting
        onReset={vi.fn()}
      />
    );

    expect(screen.getByRole('link', { name: /sign in/i })).toHaveAttribute(
      'href',
      '/login'
    );
    expect(
      screen.getByRole('link', { name: /reset your password/i })
    ).toHaveAttribute('href', '/forgot-password');

    // Resending does nothing for a confirmed account — the "Verification email
    // sent!" feedback would be a second fake success.
    expect(
      screen.queryByRole('button', { name: /resend verification/i })
    ).not.toBeInTheDocument();

    // Never assert that the account exists (enumeration).
    expect(document.body.textContent).not.toMatch(/already registered/i);
  });
});
