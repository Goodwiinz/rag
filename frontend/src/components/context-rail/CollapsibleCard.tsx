'use client';

import { cn } from '@/lib/utils';
import { ChevronDown } from 'lucide-react';
import { ReactNode, useState } from 'react';

interface CollapsibleCardProps {
  title: string;
  icon?: ReactNode;
  badge?: ReactNode;
  defaultCollapsed?: boolean;
  children: ReactNode;
  className?: string;
}

export function CollapsibleCard({
  title,
  icon,
  badge,
  defaultCollapsed = false,
  children,
  className,
}: CollapsibleCardProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  return (
    <section
      className={cn(
        'border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] rounded-lg',
        'dark:bg-[var(--nous-obsidian)] dark:border-[var(--nous-shade)]',
        className
      )}
    >
      <button
        type="button"
        onClick={() => setCollapsed((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2.5 group hover:bg-[var(--nous-aurum)]/30 dark:hover:bg-[var(--nous-ember)]/30 rounded-t-lg transition-colors"
        aria-expanded={!collapsed}
      >
        <div className="flex items-center gap-2 min-w-0">
          {icon && (
            <span
              className="grid place-items-center w-4 h-4 shrink-0 text-[var(--nous-fg-3)]"
              aria-hidden
            >
              {icon}
            </span>
          )}
          <span
            className="text-[10px] font-bold uppercase truncate text-[var(--nous-fg-3)] group-hover:text-[var(--nous-fg-2)] transition-colors"
            style={{
              fontFamily: 'var(--nous-font-mono)',
              letterSpacing: '0.18em',
            }}
          >
            {title}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {badge != null && (
            <span
              className="px-1.5 py-[1px] rounded text-[9px] tabular-nums bg-[var(--nous-bg-1)] border border-[var(--nous-border-1)] text-[var(--nous-fg-2)] dark:bg-[var(--nous-nyx)] dark:border-[var(--nous-shade)]"
              style={{
                fontFamily: 'var(--nous-font-mono)',
                letterSpacing: '0.04em',
              }}
            >
              {badge}
            </span>
          )}
          <ChevronDown
            className={cn(
              'h-3.5 w-3.5 shrink-0 transition-transform text-[var(--nous-fg-3)]',
              collapsed && '-rotate-90'
            )}
          />
        </div>
      </button>
      {!collapsed && (
        <div className="px-3 pb-3 pt-1 border-t border-[var(--nous-border-1)] dark:border-[var(--nous-shade)]">
          {children}
        </div>
      )}
    </section>
  );
}
