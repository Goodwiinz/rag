import { beforeEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, waitFor } from '@testing-library/react';
import LoginPage from '../../../../app/(auth)/login/page';

const mockPush = vi.fn();
let searchParams = new URLSearchParams();

const mockedAuth = {
  login: vi.fn(),
  isAuthenticated: true,
  isLoading: false,
};

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => mockedAuth,
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => searchParams,
}));

vi.mock('@/services/nousCliAuth', () => ({
  downloadStoredNousCliAuth: vi.fn(),
}));

describe('LoginPage post-login redirect', () => {
  beforeEach(() => {
    mockPush.mockReset();
    searchParams = new URLSearchParams();
  });

  it('redirects to /dashboard when next is a backslash-schemed path', async () => {
    // `/\evil.com` starts with a single slash, so the old hand-rolled
    // "not //" check let it through — but the browser resolves it off-origin.
    searchParams = new URLSearchParams([['next', '/\\evil.com']]);

    render(<LoginPage />);

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/dashboard'));
    expect(mockPush).not.toHaveBeenCalledWith('/\\evil.com');
  });

  it('redirects to /dashboard when next is protocol-relative', async () => {
    searchParams = new URLSearchParams([['next', '//evil.com']]);

    render(<LoginPage />);

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/dashboard'));
    expect(mockPush).not.toHaveBeenCalledWith('//evil.com');
  });

  it('follows a safe same-origin next path', async () => {
    searchParams = new URLSearchParams([['next', '/projects/abc?tab=docs']]);

    render(<LoginPage />);

    await waitFor(() =>
      expect(mockPush).toHaveBeenCalledWith('/projects/abc?tab=docs')
    );
  });
});
