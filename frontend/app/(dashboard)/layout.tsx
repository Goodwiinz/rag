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
  // any shell HTML is sent. Defense-in-depth complement to the root auth
  // middleware (PR #561).
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
