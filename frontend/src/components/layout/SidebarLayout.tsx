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
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from '@/components/ui/sidebar';
import { usePathname } from 'next/navigation';
import * as React from 'react';
import dynamic from 'next/dynamic';
import { GlobalJobCenter } from './GlobalJobCenter';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { useProjectStore } from '@/store/projectStore';

const AppSidebar = dynamic(
  () => import('./AppSidebar').then((mod) => mod.AppSidebar),
  {
    loading: () => (
      <aside className="hidden lg:block w-60 border-r border-border bg-background h-full">
        <div className="h-16 border-b border-border px-5 py-4">
          <div className="h-8 w-32 bg-muted animate-pulse rounded" />
        </div>
        <div className="p-5 space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-10 bg-muted animate-pulse rounded" />
          ))}
        </div>
      </aside>
    ),
    ssr: false, // Sidebar relies heavily on client auth state
  }
);

interface SidebarLayoutProps {
  children: React.ReactNode;
  rightPanel?: React.ReactNode;
  showBreadcrumb?: boolean;
  showHeader?: boolean;
}

// Map paths to readable names
const pathNameMap: Record<string, string> = {
  '': 'Home',
  dashboard: 'Overview',
  search: 'Search',
  documents: 'Documents',
  upload: 'Upload',
  arxiv: 'ArXiv Papers',
  analytics: 'Analytics',
  diagnostics: 'Diagnostics',
  entities: 'Entities',
  projects: 'Projects',
  realtime: 'Real-time',
  settings: 'Settings',
  team: 'Team',
  secrets: 'API Keys',
  notifications: 'Notifications',
  help: 'Help Center',
  login: 'Sign In',
  register: 'Register',
  chat: 'Chat',
  new: 'New',
  'quality-metrics-demo': 'Quality Metrics',
};

export function SidebarLayout({
  children,
  rightPanel,
  showBreadcrumb = true,
  showHeader = true,
}: SidebarLayoutProps) {
  const pathname = usePathname();
  const currentProject = useProjectStore((s) => s.currentProject);

  // Generate breadcrumb items from pathname
  const pathSegments = pathname?.split('/').filter(Boolean) || [];
  const breadcrumbItems = pathSegments.map((segment, index) => {
    const path = '/' + pathSegments.slice(0, index + 1).join('/');
    // Resolve project name for UUID segments under /projects/<id>
    const isProjectId =
      index > 0 &&
      pathSegments[index - 1] === 'projects' &&
      !pathNameMap[segment];
    const name = isProjectId
      ? currentProject?.name || 'Project'
      : pathNameMap[segment] ||
        segment.charAt(0).toUpperCase() + segment.slice(1);
    const isLast = index === pathSegments.length - 1;
    return { path, name, isLast };
  });

  return (
    <SidebarProvider defaultOpen={true} className="h-svh overflow-hidden">
      <AppSidebar />
      <SidebarInset className="!bg-background overflow-hidden">
        <div className="flex flex-1 min-h-0 overflow-hidden">
          {/* Main content column */}
          <div className="flex-1 flex flex-col min-w-0 min-h-0">
            {/* Top Header Bar */}
            {showHeader && (
              <header className="flex h-12 sm:h-14 shrink-0 items-center gap-3 border-b border-border bg-background/95 backdrop-blur px-3 sm:px-4">
                <SidebarTrigger className="h-7 w-7 text-muted-foreground hover:text-primary hover:bg-muted border border-border transition-all duration-200 rounded-md" />
                <Separator orientation="vertical" className="h-4 bg-border" />

                {showBreadcrumb && (
                  <Breadcrumb>
                    <BreadcrumbList className="text-xs">
                      {/* Show Dashboard as root, but highlight if we're on dashboard page */}
                      <BreadcrumbItem>
                        {pathname === '/dashboard' ? (
                          <BreadcrumbPage className="text-primary">
                            Dashboard
                          </BreadcrumbPage>
                        ) : (
                          <BreadcrumbLink
                            href="/dashboard"
                            className="text-muted-foreground hover:text-foreground transition-colors"
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
                            <BreadcrumbSeparator className="text-muted-foreground/50">
                              /
                            </BreadcrumbSeparator>
                            <BreadcrumbItem>
                              {item.isLast ? (
                                <BreadcrumbPage className="text-primary">
                                  {item.name}
                                </BreadcrumbPage>
                              ) : (
                                <BreadcrumbLink
                                  href={item.path}
                                  className="text-muted-foreground hover:text-foreground transition-colors"
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

                <div className="ml-auto flex items-center gap-2">
                  <ThemeToggle />
                  <GlobalJobCenter />
                </div>
              </header>
            )}

            {/* Main Content */}
            <div className="flex-1 overflow-auto">{children}</div>
          </div>

          {/* Right panel (agent chat sidebar) */}
          {rightPanel}
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
