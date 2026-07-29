import { beforeEach, describe, expect, it } from 'vitest';
import { clearSupabaseAuthCookies } from '@/lib/supabase/clearAuthCookies';

function setCookie(name: string, value: string): void {
  document.cookie = `${name}=${value}; Path=/`;
}

function clearAllCookies(): void {
  for (const raw of document.cookie.split(';')) {
    const name = raw.split('=')[0]?.trim();
    if (name) document.cookie = `${name}=; Path=/; Max-Age=0`;
  }
}

describe('clearSupabaseAuthCookies', () => {
  beforeEach(() => {
    clearAllCookies();
  });

  it('expires the auth cookie and every chunk of it', () => {
    setCookie('sb-abcdefg-auth-token', 'base');
    setCookie('sb-abcdefg-auth-token.0', 'chunk-0');
    setCookie('sb-abcdefg-auth-token.1', 'chunk-1');

    const cleared = clearSupabaseAuthCookies();

    expect(cleared.sort()).toEqual([
      'sb-abcdefg-auth-token',
      'sb-abcdefg-auth-token.0',
      'sb-abcdefg-auth-token.1',
    ]);
    expect(document.cookie).not.toContain('sb-abcdefg-auth-token');
  });

  it('leaves unrelated cookies alone', () => {
    setCookie('sb-abcdefg-auth-token', 'base');
    setCookie('theme', 'dark');
    setCookie('sb-abcdefg-auth-token-verifier', 'not-a-session');

    clearSupabaseAuthCookies();

    expect(document.cookie).toContain('theme=dark');
    expect(document.cookie).toContain('sb-abcdefg-auth-token-verifier');
  });
});
