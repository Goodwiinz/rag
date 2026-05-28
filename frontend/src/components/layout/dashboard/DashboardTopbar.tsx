'use client';

import { Button } from '@/components/ui/button';
import { useAuth } from '@/hooks/useAuth';
import { Book, ChevronRight, HelpCircle, User as UserIcon } from 'lucide-react';
import { usePathname } from 'next/navigation';

export function DashboardTopbar() {
  const pathname = usePathname();
  const { user } = useAuth();

  const getBreadcrumbs = () => {
    if (pathname?.startsWith('/chat')) return ['Goodwiinz', 'Chat Assistant'];
    if (pathname?.startsWith('/documents/upload'))
      return ['Goodwiinz', 'Documents'];
    if (pathname?.startsWith('/search'))
      return ['Goodwiinz', 'Semantic Search'];
    if (pathname?.startsWith('/settings')) return ['Goodwiinz', 'Settings'];
    return ['Goodwiinz', 'Dashboard'];
  };

  const breadcrumbs = getBreadcrumbs();

  return (
    <header className="h-16 border-b border-border bg-background/80 backdrop-blur-md flex items-center justify-between px-8 sticky top-0 z-20 ml-64 transition-all duration-300">
      {/* Breadcrumbs */}
      <div className="flex items-center gap-2 text-sm">
        <span className="text-muted-foreground font-medium">
          {breadcrumbs[0]}
        </span>
        <ChevronRight className="w-4 h-4 text-foreground" />
        <span className="text-white font-medium">{breadcrumbs[1]}</span>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          className="text-muted-foreground hover:text-white hover:bg-white/5 hidden md:flex gap-2 h-8 border border-border rounded-full px-4"
        >
          Feedback
        </Button>

        <div className="h-4 w-[1px] bg-border mx-1 hidden md:block"></div>

        <a
          href="#"
          className="flex items-center text-sm text-muted-foreground hover:text-white gap-1.5 transition-colors"
        >
          <Book className="w-4 h-4" />
          <span className="hidden sm:inline">Docs</span>
        </a>

        <a
          href="#"
          className="flex items-center text-sm text-muted-foreground hover:text-white gap-1.5 transition-colors mr-2"
        >
          <HelpCircle className="w-4 h-4" />
          <span className="hidden sm:inline">Support</span>
        </a>

        <div className="ml-2 flex items-center gap-3 pl-4 border-l border-border">
          <div className="flex flex-col items-end mr-1">
            <span className="text-xs font-medium text-white leading-none">
              {user?.email?.split('@')[0] || 'User'}
            </span>
            <span className="text-[10px] text-muted-foreground leading-none mt-1">
              Admin
            </span>
          </div>
          <div className="h-8 w-8 rounded-full bg-muted border border-border flex items-center justify-center text-muted-foreground hover:border-primary/50 cursor-pointer transition">
            <UserIcon className="w-4 h-4" />
          </div>
        </div>
      </div>
    </header>
  );
}
