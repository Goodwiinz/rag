import '@testing-library/jest-dom';
import { fireEvent, render, screen } from '@testing-library/react';
import SettingsPage from '../../../../app/(dashboard)/settings/page';

const mockedBack = jest.fn();

const mockedAuth = {
  user: {
    email: 'allocs16@gmail.com',
  },
};

jest.mock('@/hooks/useAuth', () => ({
  useAuth: () => mockedAuth,
}));

jest.mock('next/navigation', () => ({
  useRouter: () => ({
    back: mockedBack,
    push: jest.fn(),
  }),
}));

describe('Settings page', () => {
  it('renders account view by default', () => {
    render(<SettingsPage />);

    expect(screen.getByText('Settings')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'My Account' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Agent Usage' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Connected Apps' })).toBeInTheDocument();

    expect(screen.getByText('Primary email')).toBeInTheDocument();
    expect(screen.getByText('allocs16@gmail.com')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'View Plans' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Log out' })).toBeInTheDocument();
  });

  it('switches to usage and connected apps tabs', () => {
    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Agent Usage' }));
    expect(screen.getByText('Monthly Credits')).toBeInTheDocument();
    expect(screen.getByText('No usage history found')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Connected Apps' }));
    expect(screen.getByText('No connected apps yet')).toBeInTheDocument();
  });

  it('shows close button and navigates back', () => {
    render(<SettingsPage />);

    const closeButton = screen.getByRole('button', { name: 'Close settings' });
    expect(closeButton).toHaveClass('absolute');
    expect(closeButton).toHaveClass('top-4');
    expect(closeButton).toHaveClass('right-4');

    fireEvent.click(closeButton);
    expect(mockedBack).toHaveBeenCalledTimes(1);
  });

  it('uses centered and larger modal-like panel layout', () => {
    render(<SettingsPage />);

    const shell = screen.getByTestId('settings-shell');
    const panel = screen.getByTestId('settings-panel');

    expect(shell).toHaveClass('items-center');
    expect(shell).toHaveClass('justify-center');
    expect(panel).toHaveClass('max-w-6xl');
    expect(panel).toHaveClass('min-h-[700px]');
  });
});
