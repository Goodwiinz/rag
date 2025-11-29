'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';

export function Navigation() {
  const [showUserMenu, setShowUserMenu] = useState(false);
  const { user, isAuthenticated, logout } = useAuth();
  const router = useRouter();
  const userMenuRef = useRef<HTMLDivElement>(null);

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  // Close user menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setShowUserMenu(false);
      }
    };

    if (showUserMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showUserMenu]);

  if (!isAuthenticated) {
    return null;
  }

  return (
    <nav className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-14">
          {/* Logo */}
          <div className="flex items-center space-x-2">
            <div className="h-6 w-6 rounded-lg bg-primary flex items-center justify-center">
              <span className="text-primary-foreground font-bold text-xs">R</span>
            </div>
            <Link href="/" className="text-sm font-semibold text-foreground tracking-tight">
              RAG System
            </Link>
          </div>

          {/* Navigation Links */}
          <div className="hidden md:flex items-center space-x-6">
            <Link
              href="/"
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-primary"
            >
              Dashboard
            </Link>
            <Link
              href="/documents"
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-primary"
            >
              Documents
            </Link>
            <Link
              href="/search"
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-primary"
            >
              Search
            </Link>
          </div>

          {/* User Menu */}
          <div className="flex items-center">
            <div className="relative" ref={userMenuRef}>
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="flex items-center space-x-2 rounded-full border border-border bg-background px-2 py-1 hover:bg-accent hover:text-accent-foreground transition-colors"
              >
                <div className="h-6 w-6 rounded-full bg-muted flex items-center justify-center text-xs font-medium">
                  {user?.name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
                </div>
                <span className="text-xs font-medium text-muted-foreground hidden sm:block pr-1">
                  {user?.name || user?.email || 'User'}
                </span>
              </button>

              {/* Dropdown Menu */}
              {showUserMenu && (
                <div className="absolute right-0 mt-2 w-56 rounded-md border bg-popover p-1 shadow-md animate-in fade-in zoom-in-95 duration-200">
                  <div className="px-2 py-1.5 border-b border-border mb-1">
                    <p className="text-sm font-medium text-foreground">{user?.name || user?.email}</p>
                    {user?.email && user?.name && (
                      <p className="text-xs text-muted-foreground">{user?.email}</p>
                    )}
                  </div>
                  <Link
                    href="/settings"
                    className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground"
                    onClick={() => setShowUserMenu(false)}
                  >
                    Settings
                  </Link>
                  <button
                    onClick={handleLogout}
                    className="w-full text-left relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-destructive/10 hover:text-destructive"
                  >
                    Logout
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
