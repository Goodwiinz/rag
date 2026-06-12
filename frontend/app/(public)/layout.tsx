import { createClient } from '@/lib/supabase/server';
import DashboardLayoutClient from '../(dashboard)/dashboard-layout-client';
import { SimpleLayout } from '@/components/layout/SimpleLayout';

export default async function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (user) {
    return <DashboardLayoutClient>{children}</DashboardLayoutClient>;
  }

  return <SimpleLayout>{children}</SimpleLayout>;
}
