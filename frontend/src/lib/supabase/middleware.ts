import { createServerClient } from '@supabase/ssr';
import { NextResponse, type NextRequest } from 'next/server';

/**
 * Refresh the Supabase session (SSR cookie auth) from the proxy.
 *
 * `requestHeaders` (optional) lets the caller forward MUTATED request headers
 * to Next's renderer via `NextResponse.next({ request: { headers } })` — the
 * documented v16 proxy "Setting Headers" pattern. proxy.ts uses this to pass
 * the per-request CSP nonce so Next applies it to its own framework scripts.
 * Omitting it preserves the previous behavior exactly.
 */
export async function updateSession(
  request: NextRequest,
  requestHeaders?: Headers
) {
  const nextInit = {
    request: { headers: requestHeaders ?? request.headers },
  };
  let supabaseResponse = NextResponse.next(nextInit);

  const supabaseUrl =
    process.env.NEXT_PUBLIC_SUPABASE_URL || 'http://localhost:54321';
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

  const supabase = createServerClient(supabaseUrl, supabaseAnonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll().map(({ name, value }) => ({
          name,
          value,
        }));
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) =>
          request.cookies.set(name, value)
        );
        supabaseResponse = NextResponse.next(nextInit);
        cookiesToSet.forEach(({ name, value, options }) =>
          supabaseResponse.cookies.set(name, value, options)
        );
      },
    },
  });

  // Refresh the session — this is required for SSR cookie auth
  await supabase.auth.getUser();

  return supabaseResponse;
}
