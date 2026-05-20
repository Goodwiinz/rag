import { createClient } from '@/lib/supabase/server';
import { getSafeAuthRedirect } from '@/utils/authRedirect';
import { NextResponse } from 'next/server';

const VERIFY_EMAIL_PATH = '/verify-email';
const LOGIN_PATH = '/login';

function buildErrorRedirect(
  origin: string,
  code: string,
  description?: string | null
): NextResponse {
  const url = new URL(LOGIN_PATH, origin);
  url.searchParams.set('error', code);
  if (description) {
    url.searchParams.set('error_description', description);
  }
  return NextResponse.redirect(url);
}

function buildVerifyEmailErrorRedirect(
  origin: string,
  code: string,
  description?: string | null
): NextResponse {
  const url = new URL(VERIFY_EMAIL_PATH, origin);
  url.searchParams.set('error', code);
  if (description) {
    url.searchParams.set('error_description', description);
  }
  return NextResponse.redirect(url);
}

// request.url resolves to the internal K8s pod hostname when behind nginx
// ingress, which would 502 on redirect. Honor X-Forwarded-Host/Proto so the
// browser is redirected back to the public origin.
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
  const supabaseError = requestUrl.searchParams.get('error');
  const supabaseErrorDescription =
    requestUrl.searchParams.get('error_description');
  const safeRedirect = getSafeAuthRedirect(next, origin);
  const isEmailVerificationFlow = safeRedirect.startsWith(VERIFY_EMAIL_PATH);

  // Supabase redirected back with an error instead of a code
  // (e.g. expired or already-consumed confirmation link).
  if (supabaseError) {
    if (isEmailVerificationFlow) {
      return buildVerifyEmailErrorRedirect(
        origin,
        supabaseError,
        supabaseErrorDescription
      );
    }
    return buildErrorRedirect(origin, supabaseError, supabaseErrorDescription);
  }

  if (!code) {
    if (isEmailVerificationFlow) {
      return buildVerifyEmailErrorRedirect(
        origin,
        'missing_code',
        'Confirmation link is missing its verification code.'
      );
    }
    return buildErrorRedirect(
      origin,
      'missing_code',
      'Auth callback was invoked without a code.'
    );
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);

  if (error) {
    if (isEmailVerificationFlow) {
      return buildVerifyEmailErrorRedirect(
        origin,
        'exchange_failed',
        error.message
      );
    }
    return buildErrorRedirect(origin, 'exchange_failed', error.message);
  }

  return NextResponse.redirect(new URL(safeRedirect, origin));
}
