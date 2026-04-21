'use client';

import { cn } from '@/lib/utils';
import { ChevronDown } from 'lucide-react';
import { ReactNode, useState } from 'react';

interface CollapsibleCardProps {
  title: string;
  /** Optional right-aligned text in the header (e.g. "4 of 4", source count). */
  badge?: ReactNode;
  /** Start collapsed. Defaults to open. */
  defaultCollapsed?: boolean;
  children: ReactNode;
  className?: string;
}

/**
 * Cowork-style rounded card with a bold title and a chevron that
 * collapses/expands the body. Used by every panel in the ContextRail
 * so the sidebar reads as a stack of uniform cards.
 */
export function CollapsibleCard({
  title,
  badge,
  defaultCollapsed = false,
  children,
  className,
}: CollapsibleCardProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  return (
    <section
      className={cn('rounded-xl border', className)}
      style={{
        borderColor: 'var(--nous-border-1)',
        background: 'var(--nous-bg-2)',
        fontFamily: 'var(--nous-font-ui)',
      }}
    >
      <button
        type="button"
        onClick={() => setCollapsed((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 group"
        aria-expanded={!collapsed}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="text-[15px] font-semibold truncate"
            style={{ color: 'var(--nous-fg-1)' }}
          >
            {title}
          </span>
          {badge && (
            <span
              className="text-[11px] tabular-nums"
              style={{ color: 'var(--nous-fg-3)' }}
            >
              {badge}
            </span>
          )}
        </div>
        <ChevronDown
          className={cn(
            'h-4 w-4 shrink-0 transition-transform',
            collapsed && '-rotate-90'
          )}
          style={{ color: 'var(--nous-fg-3)' }}
        />
      </button>
      {!collapsed && <div className="px-4 pb-4">{children}</div>}
    </section>
  );
}
