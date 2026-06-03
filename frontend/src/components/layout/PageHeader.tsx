'use client';

import { ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  actions?: ReactNode;
}

export function PageHeader({
  title,
  subtitle,
  icon,
  actions,
}: PageHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4 mb-6">
      <div className="flex items-center gap-3">
        {icon && (
          <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-primary/10 border border-primary/20">
            {icon}
          </div>
        )}
        <div>
          <h1 className="text-2xl font-mono font-bold text-[var(--nous-fg-1)] tracking-wider">
            {title}
          </h1>
          {subtitle && (
            <p className="text-xs font-mono text-muted-foreground mt-0.5 uppercase tracking-widest">
              {subtitle}
            </p>
          )}
        </div>
      </div>
      {actions && (
        <div className="flex items-center gap-2 shrink-0">{actions}</div>
      )}
    </div>
  );
}
