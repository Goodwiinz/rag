import { describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import SettingsPage from '../../../../app/(dashboard)/settings/page';

const mockedAuth = {
  user: {
    email: 'allocs16@gmail.com',
  },
};

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => mockedAuth,
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    back: vi.fn(),
    push: vi.fn(),
  }),
}));

describe('Settings page', () => {
  it('renders the settings overview hub', () => {
    render(<SettingsPage />);

    expect(
      screen.getByRole('heading', { name: 'Settings' })
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /manage your account, workspace governance, model access, and platform controls/i
      )
    ).toBeInTheDocument();
    expect(screen.getByText('allocs16@gmail.com')).toBeInTheDocument();
    expect(screen.getByText('Workspace')).toBeInTheDocument();
    expect(screen.getByText('Role')).toBeInTheDocument();
    expect(screen.getByText('Plan')).toBeInTheDocument();
    expect(screen.getByText('Security')).toBeInTheDocument();
    expect(screen.getByText('API Access')).toBeInTheDocument();
    expect(screen.getByText('Profile & Preferences')).toBeInTheDocument();
    expect(screen.getByText('Workspace & Access')).toBeInTheDocument();
    expect(screen.getByText('Security & Compliance')).toBeInTheDocument();
    expect(screen.getByText('Usage & Billing')).toBeInTheDocument();
    expect(screen.getByText('Developer Access')).toBeInTheDocument();
    expect(screen.getByText('Connected Systems')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /open workspace & access/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /open developer access/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/last sign-in/i)).toBeInTheDocument();
    expect(screen.getByText('Audit active')).toBeInTheDocument();
    expect(screen.getByText('Encrypted')).toBeInTheDocument();
    expect(screen.getByText('Admin access')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /jump to personal controls/i })
    ).toHaveAttribute('href', '#personal-preferences');
    expect(
      screen.queryByRole('link', { name: /review profile & preferences/i })
    ).not.toBeInTheDocument();
  });

  it('shows inline preference controls and no modal affordances', () => {
    render(<SettingsPage />);

    const emailNotifications = screen.getByRole('switch', {
      name: /email notifications/i,
    });
    expect(emailNotifications).toBeChecked();

    fireEvent.click(emailNotifications);
    expect(emailNotifications).not.toBeChecked();

    expect(
      screen.queryByRole('button', { name: 'Close settings' })
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId('settings-panel')).not.toBeInTheDocument();
  });
});
