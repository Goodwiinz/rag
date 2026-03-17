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

// Pages that should not show breadcrumb
const NO_BREADCRUMB_PAGES = ['/'];

// Pages that should not show the default sidebar layout header
const NO_HEADER_PAGES = ['/chat'];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  // Check if current page should show breadcrumb
  const shouldShowBreadcrumb = !NO_BREADCRUMB_PAGES.includes(pathname || '');

  // Check if current page should show header
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
