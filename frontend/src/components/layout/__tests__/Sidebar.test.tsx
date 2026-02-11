import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Sidebar } from '../Sidebar';
import { MemoryRouter } from 'react-router-dom';

// Mock Lucide icons
jest.mock('lucide-react', () => ({
  Layers: () => <svg data-testid="layers-icon" />,
  Menu: () => <svg data-testid="menu-icon" />,
  Home: () => <svg data-testid="home-icon" />,
  Settings: () => <svg data-testid="settings-icon" />,
  __esModule: true,
  default: new Proxy(
    {},
    {
      get: () => () => <svg />,
    }
  ),
}));

// Mock navigation to avoid importing real icons
jest.mock('../navigation', () => ({
  mainNavigation: [
    { name: 'Dashboard', href: '/dashboard', icon: () => <svg /> },
  ],
  bottomNavigation: [],
}));

describe('Sidebar', () => {
  const setIsOpen = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the toggle button with correct accessibility attributes when expanded', () => {
    render(
      <MemoryRouter>
        <Sidebar isOpen={true} setIsOpen={setIsOpen} />
      </MemoryRouter>
    );

    const toggleButton = screen.getByRole('button', {
      name: /collapse sidebar/i,
    });
    expect(toggleButton).toBeInTheDocument();
    expect(toggleButton).toHaveAttribute('aria-expanded', 'true');
    expect(toggleButton).toHaveClass('focus-visible:outline-none');
    expect(toggleButton).toHaveClass('focus-visible:ring-2');
  });

  it('renders the toggle button with correct accessibility attributes when collapsed', () => {
    render(
      <MemoryRouter>
        <Sidebar isOpen={false} setIsOpen={setIsOpen} />
      </MemoryRouter>
    );

    const toggleButton = screen.getByRole('button', {
      name: /expand sidebar/i,
    });
    expect(toggleButton).toBeInTheDocument();
    expect(toggleButton).toHaveAttribute('aria-expanded', 'false');
  });

  it('calls setIsOpen when toggle button is clicked', () => {
    render(
      <MemoryRouter>
        <Sidebar isOpen={true} setIsOpen={setIsOpen} />
      </MemoryRouter>
    );

    const toggleButton = screen.getByRole('button', {
      name: /collapse sidebar/i,
    });
    fireEvent.click(toggleButton);
    expect(setIsOpen).toHaveBeenCalledWith(false);
  });
});
