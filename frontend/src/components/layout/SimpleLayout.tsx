'use client';

import { Button } from '@/components/ui/button';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import {
    BarChart3,
    Book,
    Bot,
    ChevronDown,
    Database,
    FileText,
    Home,
    LogOut,
    Search,
    Settings,
    Terminal
} from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { ReactNode, useEffect, useRef, useState } from 'react';

interface SimpleLayoutProps {
  children: ReactNode;
  showHeader?: boolean;
}

// Terminal Observatory Theme

export function SimpleLayout({ children, showHeader = true }: SimpleLayoutProps) {
  const { user, isAuthenticated, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const navItems = [
    { href: '/', label: 'Home', icon: Home },
    { href: '/search', label: 'Search', icon: Search },
    { href: '/chat', label: 'Chat', icon: Bot },
    { href: '/documents/upload', label: 'Documents', icon: FileText },
    { href: '/arxiv', label: 'ArXiv', icon: Database },
    { href: '/dashboard', label: 'Dashboard', icon: BarChart3 },
  ];

  const getInitials = (email: string | undefined) => {
    if (!email) return 'U';
    const name = email.split('@')[0];
    return name.slice(0, 2).toUpperCase();
  };

  if (!showHeader) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Terminal Observatory Header */}
      <header className="sticky top-0 z-50 border-b border-white/10 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="flex h-14 items-center justify-between px-4">
          {/* Logo/Brand */}
          <div className="flex items-center gap-6">
            <Link href="/" className="flex items-center gap-3 group">
              <div className="flex items-center justify-center w-8 h-8 rounded border border-primary/30 bg-primary/10 group-hover:border-primary/50 group-hover:bg-primary/20 transition-all">
                <Terminal className="w-4 h-4 text-primary" />
              </div>
              <div className="hidden sm:block">
                <h1 className="text-sm font-mono font-medium text-white/90 group-hover:text-primary transition-colors">
                  RAG System
                </h1>
                <p className="text-[10px] font-mono text-white/40">Terminal Observatory</p>
              </div>
            </Link>

            {/* Navigation */}
            <nav className="hidden md:flex items-center gap-1">
              {navItems.map((item) => {
                const isActive = pathname === item.href ||
                  (item.href !== '/' && pathname?.startsWith(item.href));
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-mono transition-all",
                      isActive
                        ? "text-primary bg-primary/10 border border-primary/30"
                        : "text-white/50 hover:text-white/80 hover:bg-white/5"
                    )}
                  >
                    <item.icon className="w-3.5 h-3.5" />
                    <span className="hidden lg:inline">{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* Right side */}
          <div className="flex items-center gap-3">
            {/* Quick Links */}
            <div className="hidden lg:flex items-center gap-2">
              <Link
                href="/analytics"
                className="flex items-center gap-1.5 px-2 py-1 text-[10px] font-mono text-white/40 hover:text-white/70 transition-colors"
              >
                <BarChart3 className="w-3 h-3" />
                Analytics
              </Link>
              <a
                href="#"
                className="flex items-center gap-1.5 px-2 py-1 text-[10px] font-mono text-white/40 hover:text-white/70 transition-colors"
              >
                <Book className="w-3 h-3" />
                Docs
              </a>
            </div>

            {/* Divider */}
            <div className="hidden lg:block w-px h-6 bg-white/10" />

            {/* User menu */}
            {isAuthenticated ? (
              <div className="relative" ref={userMenuRef}>
                <button
                  type="button"
                  aria-expanded={userMenuOpen}
                  aria-haspopup="true"
                  aria-label="User menu"
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  className={cn(
                    "flex items-center gap-2 px-3 py-1.5 rounded border transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50",
                    userMenuOpen
                      ? "border-primary/40 bg-primary/10"
                      : "border-white/10 bg-white/[0.02] hover:border-white/20"
                  )}
                >
                  <div className="w-6 h-6 rounded bg-gradient-to-br from-primary/20 to-primary/10 border border-primary/30 flex items-center justify-center">
                    <span className="text-[10px] font-mono font-medium text-primary">
                      {getInitials(user?.email)}
                    </span>
                  </div>
                  <div className="hidden sm:block text-left">
                    <p className="text-xs font-mono text-white/80 leading-none">
                      {user?.email?.split('@')[0] || 'User'}
                    </p>
                    <p className="text-[10px] font-mono text-white/40 leading-none mt-0.5">
                      Admin
                    </p>
                  </div>
                  <ChevronDown className={cn(
                    "w-3 h-3 text-white/40 transition-transform",
                    userMenuOpen && "rotate-180"
                  )} />
                </button>

                {/* Dropdown */}
                {userMenuOpen && (
                  <div className="absolute right-0 top-full mt-2 w-48 rounded border border-white/10 bg-card shadow-xl shadow-black/50 overflow-hidden" role="menu">
                    {/* User info */}
                    <div className="px-3 py-2 border-b border-white/10 bg-white/[0.02]">
                      <p className="text-xs font-mono text-white/80">{user?.email}</p>
                      <p className="text-[10px] font-mono text-primary">Administrator</p>
                    </div>

                    {/* Menu items */}
                    <div className="py-1">
                      <Link
                        href="/settings"
                        role="menuitem"
                        onClick={() => setUserMenuOpen(false)}
                        className="flex items-center gap-2 px-3 py-2 text-xs font-mono text-white/60 hover:text-white hover:bg-white/5 focus-visible:bg-white/5 focus-visible:outline-none transition-colors"
                      >
                        <Settings className="w-3.5 h-3.5" />
                        Settings
                      </Link>
                      <Link
                        href="/analytics"
                        role="menuitem"
                        onClick={() => setUserMenuOpen(false)}
                        className="flex items-center gap-2 px-3 py-2 text-xs font-mono text-white/60 hover:text-white hover:bg-white/5 focus-visible:bg-white/5 focus-visible:outline-none transition-colors"
                      >
                        <BarChart3 className="w-3.5 h-3.5" />
                        Analytics
                      </Link>
                    </div>

                    {/* Logout */}
                    <div className="border-t border-white/10 py-1">
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => {
                          setUserMenuOpen(false);
                          handleLogout();
                        }}
                        className="flex items-center gap-2 w-full px-3 py-2 text-xs font-mono text-red-400 hover:text-red-300 hover:bg-red-500/10 focus-visible:bg-red-500/10 focus-visible:outline-none transition-colors"
                      >
                        <LogOut className="w-3.5 h-3.5" />
                        Sign Out
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <Link href="/login">
                <Button
                  size="sm"
                  className={cn(
                    "h-8 px-4 font-mono text-xs",
                    "bg-primary/10 text-primary border border-primary/30",
                    "hover:bg-primary/20 hover:border-primary/50"
                  )}
                >
                  Sign In
                </Button>
              </Link>
            )}
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
