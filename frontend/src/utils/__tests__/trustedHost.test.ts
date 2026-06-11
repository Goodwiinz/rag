import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { isTrustedForwardedHost } from '@/utils/trustedHost';

describe('isTrustedForwardedHost (audit #13)', () => {
  const ORIG = { ...process.env };

  beforeEach(() => {
    delete process.env.NEXT_PUBLIC_FRONTEND_URL;
    delete process.env.NEXT_PUBLIC_APP_URL;
    delete process.env.TRUSTED_PROXY_HOSTS;
  });
  afterEach(() => {
    process.env = { ...ORIG };
  });

  it('rejects a forged host when nothing is allowlisted (fail closed)', () => {
    expect(isTrustedForwardedHost('evil.com')).toBe(false);
  });

  it('rejects a forged host even when a real frontend URL is configured', () => {
    process.env.NEXT_PUBLIC_FRONTEND_URL = 'https://app.nous.example';
    expect(isTrustedForwardedHost('evil.com')).toBe(false);
  });

  it('trusts the host of NEXT_PUBLIC_FRONTEND_URL', () => {
    process.env.NEXT_PUBLIC_FRONTEND_URL = 'https://app.nous.example';
    expect(isTrustedForwardedHost('app.nous.example')).toBe(true);
  });

  it('trusts hosts listed in TRUSTED_PROXY_HOSTS (comma-separated, trimmed)', () => {
    process.env.TRUSTED_PROXY_HOSTS = 'a.example, b.example';
    expect(isTrustedForwardedHost('a.example')).toBe(true);
    expect(isTrustedForwardedHost('b.example')).toBe(true);
    expect(isTrustedForwardedHost('c.example')).toBe(false);
  });

  it('returns false for an empty host', () => {
    process.env.NEXT_PUBLIC_FRONTEND_URL = 'https://app.nous.example';
    expect(isTrustedForwardedHost('')).toBe(false);
  });
});
