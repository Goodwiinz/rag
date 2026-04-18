import { createClient } from '@/lib/supabase/server';
import { getSafeAuthRedirect } from '@/utils/authRedirect';
import { NextResponse } from 'next/server';

const AUTH_CALLBACK_ERROR_REDIRECT = '/login?error=auth_callback_failed';

export async function GET(request: Request) {
  const requestUrl = new URL(request.url);
  const code = requestUrl.searchParams.get('code');
  const next = requestUrl.searchParams.get('next');
  const safeRedirect = getSafeAuthRedirect(next, requestUrl.origin);

  if (!code) {
    return NextResponse.redirect(
      new URL(AUTH_CALLBACK_ERROR_REDIRECT, requestUrl.origin)
    );
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);

  if (error) {
    return NextResponse.redirect(
      new URL(AUTH_CALLBACK_ERROR_REDIRECT, requestUrl.origin)
    );
  }

  return NextResponse.redirect(new URL(safeRedirect, requestUrl.origin));
}
