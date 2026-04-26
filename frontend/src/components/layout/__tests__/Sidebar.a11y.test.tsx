import React from 'react';
import { render } from '@/test/test-utils';
import { MemoryRouter } from 'react-router-dom';
import { expectNoA11yViolations } from '@/test/a11y';
import { Sidebar } from '../Sidebar';

// Mock Lucide icons
jest.mock('lucide-react', () => ({
  Layers: () => <svg data-testid="layers-icon" />,
  Menu: () => <svg data-testid="menu-icon" />,
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
    { name: 'Dashboard', href: '/', icon: () => <svg aria-hidden="true" /> },
    {
      name: 'Documents',
      href: '/documents',
      icon: () => <svg aria-hidden="true" />,
    },
  ],
  bottomNavigation: [
    {
      name: 'Settings',
      href: '/settings',
      icon: () => <svg aria-hidden="true" />,
    },
  ],
}));

describe('Sidebar a11y', () => {
  const mockSetIsOpen = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('has no accessibility violations when expanded', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/']}>
        <Sidebar isOpen={true} setIsOpen={mockSetIsOpen} />
      </MemoryRouter>
    );
    await expectNoA11yViolations(container);
  });

  it('has no accessibility violations when collapsed', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/']}>
        <Sidebar isOpen={false} setIsOpen={mockSetIsOpen} />
      </MemoryRouter>
    );
    await expectNoA11yViolations(container);
  });
});
