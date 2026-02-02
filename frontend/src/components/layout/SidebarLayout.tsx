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
import dynamic from 'next/dynamic';

const AppSidebar = dynamic(() => import('./AppSidebar').then(mod => mod.AppSidebar), {
  loading: () => (
    <aside className="hidden lg:block w-60 border-r border-[#1A1A1A] bg-[#080808] h-full">
      <div className="h-16 border-b border-[#1A1A1A] px-5 py-4">
        <div className="h-8 w-32 bg-[#0A0A0A] animate-pulse" />
      </div>
      <div className="p-5 space-y-3">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-10 bg-[#0A0A0A] animate-pulse" />
        ))}
      </div>
    </aside>
  ),
  ssr: false // Sidebar relies heavily on client auth state
});

interface SidebarLayoutProps {
  children: React.ReactNode;
  showBreadcrumb?: boolean;
  showHeader?: boolean;
}

// Map paths to readable names
const pathNameMap: Record<string, string> = {
  '': 'Home',
  'dashboard': 'Overview',
  'search': 'Search',
  'llm-chat': 'AI Chat',
  'documents': 'Documents',
  'upload': 'Upload',
  'arxiv': 'ArXiv Papers',
  'analytics': 'Analytics',
  'entities': 'Entities',
  'projects': 'Projects',
  'realtime': 'Real-time',
  'settings': 'Settings',
  'team': 'Team',
  'secrets': 'API Keys',
  'notifications': 'Notifications',
  'help': 'Help Center',
  'login': 'Sign In',
  'register': 'Register',
  'chat': 'Chat',
  'new': 'New',
  'quality-metrics-demo': 'Quality Metrics',
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
      <SidebarInset className="!bg-[#080808]">
        {/* Top Header Bar */}
        {showHeader && (
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-[#1A1A1A] bg-[#080808]/95 backdrop-blur px-4">
          <div className="flex items-center gap-2">
            <SidebarTrigger className="h-8 w-8 text-[#71717a] hover:text-[#00FF88] hover:bg-[#0A0A0A] border border-transparent hover:border-[#1A1A1A] transition-all duration-200 rounded-md" />
            <Separator orientation="vertical" className="h-4 bg-[#1A1A1A]" />
          </div>

          {showBreadcrumb && (
            <Breadcrumb>
              <BreadcrumbList className="font-mono text-xs">
                {/* Show Dashboard as root, but highlight if we're on dashboard page */}
                <BreadcrumbItem>
                  {pathname === '/dashboard' ? (
                    <BreadcrumbPage className="text-[#00FF88]">
                      Dashboard
                    </BreadcrumbPage>
                  ) : (
                    <BreadcrumbLink
                      href="/dashboard"
                      className="text-[#71717a] hover:text-[#fafafa] transition-colors"
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
                    <BreadcrumbSeparator className="text-[#52525b]">/</BreadcrumbSeparator>
                    <BreadcrumbItem>
                      {item.isLast ? (
                        <BreadcrumbPage className="text-[#00FF88]">
                          {item.name}
                        </BreadcrumbPage>
                      ) : (
                        <BreadcrumbLink
                          href={item.path}
                          className="text-[#71717a] hover:text-[#fafafa] transition-colors"
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
            <span className="text-sm font-mono text-[#fafafa]">{currentPage}</span>
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
