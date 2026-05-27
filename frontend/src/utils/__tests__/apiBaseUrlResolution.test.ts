import { afterEach, describe, expect, it, vi } from 'vitest';
describe('API_CONFIG base URL resolution', () => {
  const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;
  const originalApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  const originalTestOrigin = (globalThis as typeof globalThis & {
    __TEST_BROWSER_ORIGIN__?: string;
  }).__TEST_BROWSER_ORIGIN__;

  const setLocation = (origin: string) => {
    (
      globalThis as typeof globalThis & { __TEST_BROWSER_ORIGIN__?: string }
    ).__TEST_BROWSER_ORIGIN__ = origin;
  };

  const restoreEnv = (key: string, value: string | undefined) => {
    if (value === undefined) {
      delete process.env[key];
      return;
    }

    process.env[key] = value;
  };

  afterEach(() => {
    vi.resetModules();
    restoreEnv('NEXT_PUBLIC_API_URL', originalApiUrl);
    restoreEnv('NEXT_PUBLIC_API_BASE_URL', originalApiBaseUrl);
    (
      globalThis as typeof globalThis & { __TEST_BROWSER_ORIGIN__?: string }
    ).__TEST_BROWSER_ORIGIN__ = originalTestOrigin;
  });

  it('prefers the local proxy path when localhost frontend is configured with a remote API origin', async () => {
    process.env.NEXT_PUBLIC_API_URL = 'https://dev-api.gen-text.app';
    process.env.NEXT_PUBLIC_API_BASE_URL = 'https://dev-api.gen-text.app';

    setLocation('http://localhost:3000/research');

    const { API_CONFIG } = await import('@/types/api');

    expect(API_CONFIG.BASE_URL).toBe('/api/v1');
  });
});
