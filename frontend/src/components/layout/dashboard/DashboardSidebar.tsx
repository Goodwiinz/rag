'use client';

import React from 'react';
import { Folder, Settings, Users, CreditCard, Key, MessageSquare, LayoutDashboard, FileText, Search } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';

export function DashboardSidebar() {
  const pathname = usePathname();

  const projectItems = [
    { label: 'Dashboard', icon: LayoutDashboard, href: '/dashboard' },
    { label: 'Chat Assistant', icon: MessageSquare, href: '/llm-chat' },
    { label: 'Documents', icon: FileText, href: '/documents/upload' },
    { label: 'Semantic Search', icon: Search, href: '/search' },
  ];

  const orgItems = [
    { label: 'Settings', icon: Settings, href: '/settings' },
    { label: 'Team', icon: Users, href: '/team' },
    { label: 'Billing', icon: CreditCard, href: '/billing' },
    { label: 'Model Secrets', icon: Key, href: '/secrets' },
  ];

  return (
    <aside className="w-64 border-r border-border bg-card flex flex-col fixed left-0 top-0 h-full z-30">
      {/* Logo Header */}
      <div className="p-4 border-b border-border h-16 flex items-center">
        <Link href="/dashboard" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
            <Folder className="w-4 h-4 text-white" />
          </div>
          <span className="text-base font-semibold text-foreground">RAG System</span>
        </Link>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 overflow-y-auto py-6 px-3 space-y-8">
        <div>
          <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2 px-3">
            Project Settings
          </h3>
          <nav className="space-y-0.5">
            {projectItems.map((item) => {
              const isActive = pathname === item.href || pathname?.startsWith(item.href + '/');
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center px-3 py-2 text-sm font-medium rounded-md transition-all duration-200 group",
                    isActive
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                  )}
                >
                  <item.icon className={cn("w-4 h-4 mr-3 transition-colors", isActive ? "text-foreground" : "text-muted-foreground group-hover:text-foreground")} />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div>
          <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2 px-3">
            Organization Settings
          </h3>
          <nav className="space-y-0.5">
            {orgItems.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center px-3 py-2 text-sm font-medium rounded-md transition-all duration-200 group",
                    isActive
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                  )}
                >
                  <item.icon className={cn("w-4 h-4 mr-3 transition-colors", isActive ? "text-foreground" : "text-muted-foreground group-hover:text-foreground")} />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </div>
    </aside>
  );
}
