import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  logout: vi.fn(),
  push: vi.fn(),
  pathname: '/dashboard',
}));

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    user: { email: 'researcher@example.com' },
    logout: mocks.logout,
  }),
}));

vi.mock('next/navigation', () => ({
  usePathname: () => mocks.pathname,
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock('next/link', () => ({
  default: ({
    href,
    children,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock('@/components/notifications/BellPopover', () => ({
  BellPopover: () => <button aria-label="Notifications" />,
}));

import { AppRail } from '../AppRail';

describe('AppRail', () => {
  it('lets the user sign out from the rail', () => {
    render(<AppRail />);

    fireEvent.click(screen.getByRole('button', { name: /sign out/i }));

    expect(mocks.logout).toHaveBeenCalledTimes(1);
    expect(mocks.push).toHaveBeenCalledWith('/login');
  });
});
