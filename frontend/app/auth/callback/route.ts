import { createClient } from '@/lib/supabase/server';
import { getSafeAuthRedirect } from '@/utils/authRedirect';
import { NextResponse } from 'next/server';

const AUTH_CALLBACK_ERROR_REDIRECT = '/login?error=auth_callback_failed';

function getPublicOrigin(request: Request): string {
  const headers = new Headers(request.headers);
  const forwardedHost = headers.get('x-forwarded-host');
  const forwardedProto = headers.get('x-forwarded-proto') || 'https';
  if (forwardedHost) {
    return `${forwardedProto}://${forwardedHost}`;
  }
  return new URL(request.url).origin;
}

export async function GET(request: Request) {
  const requestUrl = new URL(request.url);
  const origin = getPublicOrigin(request);
  const code = requestUrl.searchParams.get('code');
  const next = requestUrl.searchParams.get('next');
  const safeRedirect = getSafeAuthRedirect(next, origin);

  if (!code) {
    return NextResponse.redirect(
      new URL(AUTH_CALLBACK_ERROR_REDIRECT, origin)
    );
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);

  if (error) {
    return NextResponse.redirect(
      new URL(AUTH_CALLBACK_ERROR_REDIRECT, origin)
    );
  }

  return NextResponse.redirect(new URL(safeRedirect, origin));
}
