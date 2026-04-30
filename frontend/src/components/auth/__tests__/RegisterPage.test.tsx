import { beforeEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import RegisterPage from '../../../../app/(auth)/register/page';

type RegisterResult = {
  requiresEmailConfirmation: boolean;
};

const mockPush = vi.fn();
const mockRegister = vi.fn<Promise<RegisterResult>, [unknown]>();

const mockedAuth = {
  register: mockRegister,
  isAuthenticated: false,
  isLoading: false,
  pendingEmailConfirmation: false,
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
    fireEvent.change(screen.getByLabelText(/identity protocol/i), {
      target: { value: 'ada@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/organization/i), {
      target: { value: 'Analytical Engine' },
    });
    fireEvent.change(screen.getByLabelText(/security key/i), {
      target: { value: 'SecurePass123!' },
    });
    fireEvent.change(screen.getByLabelText(/verify key/i), {
      target: { value: 'SecurePass123!' },
    });

    fireEvent.click(screen.getByRole('button', { name: /commit identity/i }));

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledTimes(1);
    });
    expect(mockPush).not.toHaveBeenCalled();
    expect(
      await screen.findByRole('heading', { name: /verify your identity/i })
    ).toBeInTheDocument();
  });
});
