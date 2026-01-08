'use client';

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb';
import { Separator } from '@/components/ui/separator';
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar';
import { usePathname } from 'next/navigation';
import * as React from 'react';
import { AppSidebar } from './AppSidebar';

interface SidebarLayoutProps {
  children: React.ReactNode;
  showBreadcrumb?: boolean;
  showHeader?: boolean;
}

// Map paths to readable names
const pathNameMap: Record<string, string> = {
  '': 'Home',
  'dashboard': 'Dashboard',
  'search': 'Search',
  'llm-chat': 'AI Chat',
  'documents': 'Documents',
  'upload': 'Upload',
  'arxiv': 'ArXiv Papers',
  'analytics': 'Analytics',
  'realtime': 'Real-time',
  'settings': 'Settings',
  'team': 'Team',
  'secrets': 'API Keys',
  'notifications': 'Notifications',
  'help': 'Help Center',
  'login': 'Sign In',
  'register': 'Register',
  'chat': 'Chat',
};

export function SidebarLayout({ children, showBreadcrumb = true, showHeader = true }: SidebarLayoutProps) {
  const pathname = usePathname();

  // Generate breadcrumb items from pathname
  const pathSegments = pathname?.split('/').filter(Boolean) || [];
  const breadcrumbItems = pathSegments.map((segment, index) => {
    const path = '/' + pathSegments.slice(0, index + 1).join('/');
    const name = pathNameMap[segment] || segment.charAt(0).toUpperCase() + segment.slice(1);
    const isLast = index === pathSegments.length - 1;
    return { path, name, isLast };
  });

  // Get current page title
  const currentPage = breadcrumbItems.length > 0
    ? breadcrumbItems[breadcrumbItems.length - 1].name
    : 'Dashboard';

  return (
    <SidebarProvider defaultOpen={true}>
      <AppSidebar />
      <SidebarInset className="!bg-[#0a0a0f]">
        {/* Top Header Bar */}
        {showHeader && (
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-white/10 bg-[#0a0a0f]/95 backdrop-blur supports-[backdrop-filter]:bg-[#0a0a0f]/80 px-4">
          <div className="flex items-center gap-2">
            <SidebarTrigger className="h-7 w-7 text-white/60 hover:text-white hover:bg-white/5" />
            <Separator orientation="vertical" className="h-4 bg-white/10" />
          </div>

          {showBreadcrumb && (
            <Breadcrumb>
              <BreadcrumbList className="font-mono text-xs">
                {/* Show Dashboard as root, but highlight if we're on dashboard page */}
                <BreadcrumbItem>
                  {pathname === '/dashboard' ? (
                    <BreadcrumbPage className="text-[#00ff9f]">
                      Dashboard
                    </BreadcrumbPage>
                  ) : (
                    <BreadcrumbLink
                      href="/dashboard"
                      className="text-white/40 hover:text-white/70 transition-colors"
                    >
                      Dashboard
                    </BreadcrumbLink>
                  )}
                </BreadcrumbItem>
                {/* Filter out dashboard from breadcrumb items to avoid Dashboard / Dashboard */}
                {breadcrumbItems
                  .filter((item) => item.path !== '/dashboard')
                  .map((item) => (
                  <React.Fragment key={item.path}>
                    <BreadcrumbSeparator className="text-white/20">/</BreadcrumbSeparator>
                    <BreadcrumbItem>
                      {item.isLast ? (
                        <BreadcrumbPage className="text-[#00ff9f]">
                          {item.name}
                        </BreadcrumbPage>
                      ) : (
                        <BreadcrumbLink
                          href={item.path}
                          className="text-white/40 hover:text-white/70 transition-colors"
                        >
                          {item.name}
                        </BreadcrumbLink>
                      )}
                    </BreadcrumbItem>
                  </React.Fragment>
                ))}
              </BreadcrumbList>
            </Breadcrumb>
          )}

          {/* Page Title (mobile) */}
          <div className="ml-auto md:hidden">
            <span className="text-sm font-mono text-white/80">{currentPage}</span>
          </div>
        </header>
        )}

        {/* Main Content */}
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
