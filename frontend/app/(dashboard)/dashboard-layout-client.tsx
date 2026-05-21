'use client';

import dynamic from 'next/dynamic';
import { SidebarLayout } from '@/components/layout/SidebarLayout';
import { usePathname } from 'next/navigation';

const GlobalAgentChat = dynamic(
  () =>
    import('@/components/agent-chat/GlobalAgentChat').then(
      (m) => m.GlobalAgentChat
    ),
  { ssr: false }
);

const NO_BREADCRUMB_PAGES = ['/'];
const NO_HEADER_PAGES = ['/chat'];

export default function DashboardLayoutClient({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const shouldShowBreadcrumb = !NO_BREADCRUMB_PAGES.includes(pathname || '');
  const shouldShowHeader = !NO_HEADER_PAGES.some(
    (page) => pathname === page || pathname?.startsWith(page + '/')
  );

  return (
    <SidebarLayout
      showBreadcrumb={shouldShowBreadcrumb}
      showHeader={shouldShowHeader}
      rightPanel={<GlobalAgentChat />}
    >
      {children}
    </SidebarLayout>
  );
}
