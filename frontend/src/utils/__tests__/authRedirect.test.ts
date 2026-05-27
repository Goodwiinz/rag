import { describe, expect, it } from 'vitest';
import { getSafeAuthRedirect } from '@/utils/authRedirect';

describe('getSafeAuthRedirect', () => {
  it('falls back to dashboard when next points to an external origin', () => {
    expect(
      getSafeAuthRedirect('https://evil.example/phish', 'http://localhost:3000')
    ).toBe('/dashboard');
  });

  it('preserves internal destinations and query strings', () => {
    expect(
      getSafeAuthRedirect(
        '/verify-email?from=signup',
        'http://localhost:3000'
      )
    ).toBe('/verify-email?from=signup');
  });
});
