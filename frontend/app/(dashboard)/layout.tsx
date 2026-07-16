import { Metadata } from 'next';
import { redirect } from 'next/navigation';
import { createClient } from '@/lib/supabase/server';
import DashboardLayoutClient from './dashboard-layout-client';

export const metadata: Metadata = {
  title: {
    template: '%s | NOUS',
    default: 'Dashboard | NOUS',
  },
};

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Server-side route guard (audit #11): this RSC layout previously delegated
  // straight to a client component, so every (dashboard) route rendered its
  // full shell for anonymous visitors and relied entirely on client-side
  // fetches failing. Validate the session on the server with getUser() (which
  // verifies the JWT with Supabase, not just the cookie) and redirect before
  // any shell HTML is sent.
  //
  // This is the SOLE server-side auth gate for (dashboard) routes (AU8,
  // 2026-07-16) — proxy.ts (root middleware) only refreshes the Supabase
  // session cookie and sets the CSP nonce; it has no getUser()-gated
  // redirect. (A prior version of this comment claimed a "root auth
  // middleware (PR #561)" complement — PR #561 never touched proxy.ts or
  // src/lib/supabase/middleware.ts, and the root middleware has never
  // redirected unauthenticated requests since it was first added: the claim
  // was stale/inaccurate, not a regression from a real removal.) Any new
  // top-level route that should require auth MUST live under this
  // (dashboard) layout (or add an equivalent getUser() guard of its own) —
  // there is no middleware backstop.
  const supabase = await createClient();
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();
  // Surface WHY there's no user: a network/verification failure (unreachable
  // auth endpoint, bad key, GoTrue 5xx) is otherwise indistinguishable from a
  // genuinely-anonymous visitor — both fall through to redirect('/login').
  if (error) {
    console.error(
      '[(dashboard)/layout] getUser failed:',
      error.status,
      error.message
    );
  }
  if (!user) {
    redirect('/login');
  }

  return <DashboardLayoutClient>{children}</DashboardLayoutClient>;
}
