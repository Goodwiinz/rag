'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import { Book, HelpCircle, User as UserIcon } from 'lucide-react';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { Separator } from '@/components/ui/separator';
import { Button } from '@/components/ui/button';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb';
import { useAuth } from '@/hooks/useAuth';

interface DashboardLayoutProps {
  children: React.ReactNode;
  fullHeight?: boolean;
}

export function DashboardLayout({ children, fullHeight = false }: DashboardLayoutProps) {
  const pathname = usePathname();
  const { user } = useAuth();

  const getBreadcrumbs = () => {
    if (pathname?.startsWith('/llm-chat')) return { section: 'Project', page: 'Chat Assistant' };
    if (pathname?.startsWith('/documents/upload')) return { section: 'Project', page: 'Documents' };
    if (pathname?.startsWith('/search')) return { section: 'Project', page: 'Semantic Search' };
    if (pathname?.startsWith('/settings')) return { section: 'Organization', page: 'Settings' };
    if (pathname?.startsWith('/team')) return { section: 'Organization', page: 'Team' };
    if (pathname?.startsWith('/billing')) return { section: 'Organization', page: 'Billing' };
    if (pathname?.startsWith('/secrets')) return { section: 'Organization', page: 'Model Secrets' };
    return { section: 'Project', page: 'Dashboard' };
  };

  const breadcrumb = getBreadcrumbs();

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="flex flex-col h-screen">
        {/* Header */}
        <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem className="hidden md:block">
                <BreadcrumbLink href="#">{breadcrumb.section}</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator className="hidden md:block" />
              <BreadcrumbItem>
                <BreadcrumbPage>{breadcrumb.page}</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>

          {/* Right side actions */}
          <div className="ml-auto flex items-center gap-3">
            <Button variant="ghost" size="sm" className="hidden md:flex h-7 text-xs">
              Feedback
            </Button>

            <Separator orientation="vertical" className="h-4 hidden md:block" />

            <a href="#" className="flex items-center text-xs text-muted-foreground hover:text-foreground gap-1 transition-colors">
              <Book className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Docs</span>
            </a>

            <a href="#" className="flex items-center text-xs text-muted-foreground hover:text-foreground gap-1 transition-colors">
              <HelpCircle className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Support</span>
            </a>

            <Separator orientation="vertical" className="h-4" />

            <div className="flex items-center gap-2">
              <div className="flex flex-col items-end">
                <span className="text-xs font-medium leading-none">{user?.email?.split('@')[0] || 'User'}</span>
                <span className="text-[10px] text-muted-foreground leading-none mt-0.5">Admin</span>
              </div>
              <div className="h-7 w-7 rounded-full bg-muted border flex items-center justify-center text-muted-foreground hover:border-foreground/20 cursor-pointer transition">
                <UserIcon className="w-3.5 h-3.5" />
              </div>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <div className={fullHeight ? 'flex-1 overflow-hidden' : 'flex-1 overflow-auto p-4 md:p-6'}>
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
