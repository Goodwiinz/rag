'use client';

import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { BarChart3, Book, HelpCircle, User as UserIcon, LogOut } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { ReactNode } from 'react';

interface SimpleLayoutProps {
  children: ReactNode;
  showHeader?: boolean;
}

export function SimpleLayout({ children, showHeader = true }: SimpleLayoutProps) {
  const { user, logout } = useAuth();
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  if (!showHeader) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-50">
        <div className="flex h-16 items-center justify-between px-6">
          {/* Logo/Brand */}
          <div className="flex items-center gap-3">
            <div className="flex aspect-square size-9 items-center justify-center rounded-lg bg-gradient-to-br from-amber-500 to-orange-500 shadow-lg shadow-amber-500/25">
              <span className="text-white font-bold text-lg">RAG</span>
            </div>
            <div>
              <h1 className="text-lg font-semibold">Multimodal RAG System</h1>
              <p className="text-xs text-muted-foreground">Enterprise</p>
            </div>
          </div>

          {/* Right side actions */}
          <div className="flex items-center gap-4">
            <a
              href="/analytics"
              className="flex items-center text-xs text-muted-foreground hover:text-foreground gap-1.5 transition-colors"
            >
              <BarChart3 className="w-4 h-4" />
              <span className="hidden sm:inline">Analytics</span>
            </a>

            <Button variant="ghost" size="sm" className="hidden lg:flex text-xs">
              Feedback
            </Button>

            <a
              href="#"
              className="flex items-center text-xs text-muted-foreground hover:text-foreground gap-1.5 transition-colors"
            >
              <Book className="w-4 h-4" />
              <span className="hidden sm:inline">Docs</span>
            </a>

            <a
              href="#"
              className="flex items-center text-xs text-muted-foreground hover:text-foreground gap-1.5 transition-colors"
            >
              <HelpCircle className="w-4 h-4" />
              <span className="hidden sm:inline">Support</span>
            </a>

            {/* User menu */}
            <div className="flex items-center gap-2 pl-4 border-l">
              <div className="flex flex-col items-end">
                <span className="text-xs font-medium leading-none">
                  {user?.email?.split('@')[0] || 'User'}
                </span>
                <span className="text-[10px] text-muted-foreground leading-none mt-0.5">
                  Admin
                </span>
              </div>
              <div className="h-8 w-8 rounded-full bg-gradient-to-br from-primary/10 to-primary/20 border border-primary/20 flex items-center justify-center text-primary hover:border-primary/40 cursor-pointer transition-all group">
                <UserIcon className="w-4 h-4" />
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={handleLogout}
                title="Logout"
              >
                <LogOut className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1">
        {children}
      </main>
    </div>
  );
}