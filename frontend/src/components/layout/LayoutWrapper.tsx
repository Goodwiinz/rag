'use client';

import { usePathname } from 'next/navigation';
import { SidebarLayout } from './SidebarLayout';
import { ReactNode } from 'react';

interface LayoutWrapperProps {
  children: ReactNode;
}

// Pages that should NOT have the sidebar
const NO_SIDEBAR_PAGES = [
  '/',           // Landing page - standalone marketing page
  '/login',
  '/register',
  '/forgot-password',
  '/reset-password',
  '/verify-email',
];

// Pages that should not show breadcrumb
const NO_BREADCRUMB_PAGES = [
  '/',
];

export function LayoutWrapper({ children }: LayoutWrapperProps) {
  const pathname = usePathname();

  // Check if current page should have sidebar
  const shouldShowSidebar = !NO_SIDEBAR_PAGES.some(
    page => pathname === page || pathname?.startsWith(page + '/')
  );

  // Check if current page should show breadcrumb
  const shouldShowBreadcrumb = !NO_BREADCRUMB_PAGES.includes(pathname || '');

  if (!shouldShowSidebar) {
    // Return children wrapped in a basic dark container for auth pages
    return (
      <div className="min-h-screen bg-[#0a0a0f]">
        {children}
      </div>
    );
  }

  return (
    <SidebarLayout showBreadcrumb={shouldShowBreadcrumb}>
      {children}
    </SidebarLayout>
  );
}