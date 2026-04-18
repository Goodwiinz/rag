'use client';

import { usePathname } from 'next/navigation';
import { ReactNode } from 'react';
import { SidebarLayout } from './SidebarLayout';

interface LayoutWrapperProps {
  children: ReactNode;
}

// Pages that should NOT have the sidebar
const NO_SIDEBAR_PAGES = [
  '/', // Landing page - standalone marketing page
  '/login',
  '/register',
  '/forgot-password',
  '/reset-password',
  '/verify-email',
];

// Pages that should not show breadcrumb
const NO_BREADCRUMB_PAGES = ['/'];

// Pages that should not show the default sidebar layout header (e.g. chat has its own)
const NO_HEADER_PAGES = ['/chat'];

export function LayoutWrapper({ children }: LayoutWrapperProps) {
  const pathname = usePathname();

  // Check if current page should have sidebar
  const shouldShowSidebar = !NO_SIDEBAR_PAGES.some(
    (page) => pathname === page || pathname?.startsWith(page + '/')
  );

  // Check if current page should show breadcrumb
  const shouldShowBreadcrumb = !NO_BREADCRUMB_PAGES.includes(pathname || '');

  // Check if current page should show header
  const shouldShowHeader = !NO_HEADER_PAGES.some(
    (page) => pathname === page || pathname?.startsWith(page + '/')
  );

  if (!shouldShowSidebar) {
    // Return children wrapped in a basic dark container for auth pages
    return <div className="min-h-screen bg-background">{children}</div>;
  }

  return (
    <SidebarLayout
      showBreadcrumb={shouldShowBreadcrumb}
      showHeader={shouldShowHeader}
    >
      {children}
    </SidebarLayout>
  );
}
