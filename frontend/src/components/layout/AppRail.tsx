'use client';

import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';
import {
  BarChart3,
  BookOpen,
  FileText,
  FlaskConical,
  LayoutGrid,
  MessageSquare,
  Network,
  Search,
  Settings,
  Workflow,
} from 'lucide-react';
import Link from 'next/link';
import { BellPopover } from '@/components/notifications/BellPopover';
import { usePathname } from 'next/navigation';

interface RailButtonProps {
  icon: LucideIcon;
  tip: string;
  href: string;
  active?: boolean;
  badge?: number;
  dot?: boolean;
}

function RailButton({
  icon: Icon,
  tip,
  href,
  active,
  badge,
  dot,
}: RailButtonProps) {
  return (
    <Link
      href={href}
      aria-label={tip}
      aria-current={active ? 'page' : undefined}
      data-tip={tip}
      className={cn(
        'rail-btn relative flex items-center justify-center w-9 h-9 rounded-lg transition-colors duration-150',
        active
          ? 'bg-[var(--nous-aurum)] text-[var(--nous-sol-safe)] dark:bg-[var(--nous-ember)] dark:text-[var(--nous-helios)]'
          : 'text-[var(--nous-fg-3)] hover:bg-[var(--nous-aurum)] hover:text-[var(--nous-sol-safe)] dark:hover:bg-[var(--nous-ember)] dark:hover:text-[var(--nous-helios)]'
      )}
    >
      {active && (
        <span className="absolute -left-[10px] top-2 bottom-2 w-0.5 rounded-r bg-[var(--nous-sol)] dark:bg-[var(--nous-helios)]" />
      )}
      <Icon className="w-4 h-4 rail-icon" />
      {badge != null && badge > 0 && (
        <span className="absolute top-[3px] right-[2px] min-w-[14px] h-[14px] px-[3px] flex items-center justify-center rounded-full bg-[var(--nous-sol)] text-white text-[9px] font-bold font-[var(--nous-font-mono)] shadow-[0_0_0_2px_var(--nous-bg-2)] dark:shadow-[0_0_0_2px_var(--nous-nyx)]">
          {badge}
        </span>
      )}
      {dot && (
        <span className="absolute top-[7px] right-[7px] w-1.5 h-1.5 rounded-full bg-[var(--nous-sol)] shadow-[0_0_0_2px_var(--nous-bg-2)] dark:shadow-[0_0_0_2px_var(--nous-nyx)]" />
      )}
    </Link>
  );
}

export function AppRail() {
  const pathname = usePathname();
  const { user } = useAuth();

  const isActive = (url: string) => {
    if (url === '/dashboard') return pathname === '/dashboard';
    return pathname?.startsWith(url) ?? false;
  };

  const getInitials = (email: string | undefined) => {
    if (!email) return 'U';
    return email.split('@')[0].slice(0, 2).toUpperCase();
  };

  return (
    <aside
      aria-label="Primary"
      className="flex flex-col items-center w-14 h-full shrink-0 py-3 gap-1 border-r border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] dark:bg-[var(--nous-nyx)] dark:border-[var(--nous-shade)]"
    >
      {/* Brand mark */}
      <Link
        href="/dashboard"
        aria-label="NOUS home"
        className="relative flex items-center justify-center w-8 h-8 rounded-lg bg-[var(--nous-erebus)] dark:bg-[var(--nous-sol)] shadow-sm mb-1"
      >
        <span
          className="text-white dark:text-[var(--nous-nyx)] text-[15px] font-bold leading-none"
          style={{
            fontFamily: 'var(--nous-font-body)',
            letterSpacing: '-0.02em',
          }}
        >
          N
        </span>
        <span className="absolute inset-[-2px] rounded-[10px] border border-[var(--nous-aurum)] dark:border-[var(--nous-ember)] opacity-55 pointer-events-none" />
      </Link>

      {/* Divider */}
      <div className="w-[22px] h-px bg-[var(--nous-border-1)] dark:bg-[var(--nous-shade)] my-1.5" />

      {/* Navigation — hub */}
      <RailButton
        icon={LayoutGrid}
        tip="Overview"
        href="/dashboard"
        active={isActive('/dashboard')}
      />
      <RailButton
        icon={MessageSquare}
        tip="Chat"
        href="/chat"
        active={isActive('/chat')}
      />
      <RailButton
        icon={FileText}
        tip="Documents"
        href="/documents"
        active={isActive('/documents')}
      />
      <RailButton
        icon={Search}
        tip="Search"
        href="/search"
        active={isActive('/search')}
      />

      {/* Divider — knowledge */}
      <div className="w-[22px] h-px bg-[var(--nous-border-1)] dark:bg-[var(--nous-shade)] my-1.5" />

      <RailButton
        icon={BookOpen}
        tip="ArXiv Papers"
        href="/arxiv"
        active={isActive('/arxiv')}
      />
      <RailButton
        icon={Network}
        tip="Knowledge graph"
        href="/entities"
        active={isActive('/entities')}
      />
      <RailButton
        icon={FlaskConical}
        tip="Research"
        href="/research"
        active={isActive('/research')}
      />
      <RailButton
        icon={Workflow}
        tip="Research Engine"
        href="/research-engine"
        active={isActive('/research-engine')}
      />

      {/* Divider — system */}
      <div className="w-[22px] h-px bg-[var(--nous-border-1)] dark:bg-[var(--nous-shade)] my-1.5" />

      <RailButton
        icon={BarChart3}
        tip="Analytics"
        href="/analytics"
        active={isActive('/analytics')}
      />

      {/* Divider */}
      <div className="w-[22px] h-px bg-[var(--nous-border-1)] dark:bg-[var(--nous-shade)] my-1.5" />

      <BellPopover active={isActive('/notifications')} />
      <RailButton
        icon={Settings}
        tip="Settings"
        href="/settings"
        active={isActive('/settings')}
      />

      {/* Spacer */}
      <div className="flex-1" />

      {/* User avatar */}
      <Link
        href="/settings"
        aria-label="Account"
        className="relative flex items-center justify-center w-8 h-8 rounded-full bg-gradient-to-br from-[var(--nous-sol)] to-[var(--nous-helios)] shadow-[0_0_0_2px_var(--nous-bg-2),0_2px_4px_rgba(212,160,57,0.2)] dark:shadow-[0_0_0_2px_var(--nous-nyx),0_2px_4px_rgba(212,160,57,0.2)]"
      >
        <span
          className="text-white text-[11px] font-semibold leading-none"
          style={{ fontFamily: 'var(--nous-font-ui)' }}
        >
          {getInitials(user?.email)}
        </span>
        <span className="absolute -bottom-[1px] -right-[1px] w-[9px] h-[9px] rounded-full bg-[var(--nous-terra)] shadow-[0_0_0_2px_var(--nous-bg-2)] dark:shadow-[0_0_0_2px_var(--nous-nyx)]" />
      </Link>
    </aside>
  );
}
