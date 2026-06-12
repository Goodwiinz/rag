/**
 * Shared, build-time-pinned auth cookie name for the Supabase SSR clients.
 *
 * @supabase/ssr derives its cookie/storage key from the Supabase URL's hostname
 * (`sb-<hostname>-auth-token`). That is fine when the browser and the Next
 * server reach Supabase at the same URL — but the e2e stack can't: Playwright
 * runs on the runner host (NEXT_PUBLIC_SUPABASE_URL=http://localhost:8999) while
 * the Next server runs in a container (SUPABASE_SERVER_URL=http://auth-proxy).
 * Different hostnames → different cookie names → the server never finds the
 * session the browser wrote, so getUser() returns "Auth session missing" and
 * every authed route bounces to /login.
 *
 * Setting NEXT_PUBLIC_AUTH_COOKIE_NAME pins the same storage key on both
 * clients, so the cookie matches regardless of URL. It is unset in production —
 * there the URL-derived default is kept, so behavior is unchanged (and existing
 * sessions are not invalidated). The e2e frontend image sets it.
 */
export function authCookieOptions(): { name: string } | undefined {
  const name = process.env.NEXT_PUBLIC_AUTH_COOKIE_NAME;
  return name ? { name } : undefined;
}
