'use client';

import { cn } from '@/lib/utils';
import { Files, LayoutDashboard, MessageSquare, Search } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const TABS = [
  { href: '/chat', label: 'Chat', icon: MessageSquare },
  { href: '/search', label: 'Search', icon: Search },
  { href: '/documents', label: 'Docs', icon: Files },
  { href: '/dashboard', label: 'Home', icon: LayoutDashboard },
] as const;

export function MobileTabBar() {
  const pathname = usePathname();

  return (
    <nav
      className="md:hidden fixed bottom-0 left-0 right-0 z-40 border-t border-[var(--nous-border-1)] bg-[var(--nous-bg-1)]/95 backdrop-blur-md safe-area-bottom"
      style={{ fontFamily: 'var(--nous-font-ui)' }}
    >
      <div className="flex items-center justify-around h-14">
        {TABS.map(({ href, label, icon: Icon }) => {
          const isActive =
            pathname === href || pathname?.startsWith(href + '/');

          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex flex-col items-center justify-center gap-1 flex-1 h-full transition-colors',
                isActive
                  ? 'text-[var(--nous-sol)]'
                  : 'text-[var(--nous-fg-3)] active:text-[var(--nous-fg-1)]'
              )}
            >
              <Icon className="w-5 h-5" strokeWidth={isActive ? 2.2 : 1.8} />
              <span className={cn('text-[10px]', isActive && 'font-semibold')}>
                {label}
              </span>
              {isActive && (
                <div className="absolute bottom-1 w-1 h-1 rounded-full bg-[var(--nous-sol)]" />
              )}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
