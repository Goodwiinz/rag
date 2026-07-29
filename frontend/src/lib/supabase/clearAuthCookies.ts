import { authCookieOptions } from './cookieOptions';

/**
 * Default @supabase/ssr browser storage key: `sb-<hostname>-auth-token`,
 * optionally suffixed with a chunk index (`.0`, `.1`, …) for large sessions.
 */
const DEFAULT_AUTH_COOKIE_NAME = /^sb-.+-auth-token$/;
const CHUNK_SUFFIX = /\.(?:0|[1-9][0-9]*)$/;

function isChunkOf(cookieName: string, storageKey: string): boolean {
  if (cookieName === storageKey) return true;
  return (
    cookieName.startsWith(`${storageKey}.`) &&
    CHUNK_SUFFIX.test(cookieName.slice(storageKey.length))
  );
}

function isAuthCookieName(cookieName: string, storageKey?: string): boolean {
  if (storageKey && isChunkOf(cookieName, storageKey)) return true;
  return DEFAULT_AUTH_COOKIE_NAME.test(cookieName.replace(CHUNK_SUFFIX, ''));
}

/**
 * Best-effort removal of the Supabase SSR auth cookie (and its chunks) from the
 * browser.
 *
 * supabase-js only clears the local session when its `/logout` call succeeds
 * (or is rejected with 401/403/404). On a network failure or a 5xx it returns
 * `{ error }` BEFORE `_removeSession()`, leaving the cookie in place — so the
 * app renders "signed out" while the very next reload restores the session.
 * Calling this on that failure path makes the signed-out state real.
 *
 * Returns the names of the cookies it expired (empty outside a browser).
 */
export function clearSupabaseAuthCookies(): string[] {
  if (typeof document === 'undefined') return [];

  const storageKey = authCookieOptions()?.name;
  const secure =
    typeof location !== 'undefined' && location.protocol === 'https:'
      ? '; Secure'
      : '';
  const cleared: string[] = [];

  for (const rawCookie of document.cookie.split(';')) {
    const name = rawCookie.split('=')[0]?.trim();
    if (!name || !isAuthCookieName(name, storageKey)) continue;
    document.cookie = `${name}=; Path=/; Max-Age=0; SameSite=Lax${secure}`;
    cleared.push(name);
  }

  return cleared;
}
