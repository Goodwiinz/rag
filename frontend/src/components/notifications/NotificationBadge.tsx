import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';
import type { NotificationChannel } from './types';

/* ─── Dot badge: bare red signal on a nav icon ─── */

interface DotBadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

const DotBadge = React.forwardRef<HTMLDivElement, DotBadgeProps>(
  ({ className, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'relative inline-flex items-center justify-center',
        'h-8 w-8 rounded-[var(--nous-radius-md)]',
        'bg-[var(--nous-bg-2)] border border-[var(--nous-border-1)]',
        'text-[var(--nous-fg-2)]',
        'dark:bg-[var(--nous-obsidian)] dark:border-[var(--nous-shade)]',
        className
      )}
      {...props}
    >
      {children}
      <span
        className={cn(
          'absolute top-1.5 right-1.5',
          'h-1.5 w-1.5 rounded-full',
          'bg-[var(--nous-mars)]',
          'shadow-[0_0_0_2px_var(--nous-bg-2)]',
          'dark:shadow-[0_0_0_2px_var(--nous-obsidian)]'
        )}
      />
    </div>
  )
);
DotBadge.displayName = 'DotBadge';

/* ─── Count badge: numeric chip on a nav icon ─── */

interface CountBadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  count: number | string;
  children: React.ReactNode;
}

const CountBadge = React.forwardRef<HTMLDivElement, CountBadgeProps>(
  ({ className, count, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'relative inline-flex items-center justify-center',
        'h-8 w-8 rounded-[var(--nous-radius-md)]',
        'bg-[var(--nous-bg-2)] border border-[var(--nous-border-1)]',
        'text-[var(--nous-fg-2)]',
        'dark:bg-[var(--nous-obsidian)] dark:border-[var(--nous-shade)]',
        className
      )}
      {...props}
    >
      {children}
      <span
        className={cn(
          'absolute -top-[5px] -right-[5px]',
          'min-w-[18px] h-[18px] px-[5px]',
          'bg-[var(--nous-sol)] text-[var(--nous-erebus)]',
          'dark:bg-[var(--nous-helios)]',
          'rounded-full',
          'font-[family-name:var(--nous-font-mono)] text-[10px] font-bold tracking-[0.02em]',
          'inline-flex items-center justify-center',
          'shadow-[0_0_0_2px_var(--nous-bg-1)]',
          'dark:shadow-[0_0_0_2px_var(--nous-nyx)]'
        )}
      >
        {count}
      </span>
    </div>
  )
);
CountBadge.displayName = 'CountBadge';

/* ─── Status pill: labeled mono, all-caps ─── */

const statusPillVariants = cva(
  [
    'inline-flex items-center gap-1.5',
    'px-2.5 py-[3px] rounded-full',
    'font-[family-name:var(--nous-font-mono)] text-[10px] tracking-[0.12em] uppercase font-medium',
  ].join(' '),
  {
    variants: {
      variant: {
        default:
          'bg-[var(--nous-aurum)] text-[var(--nous-sol-safe)] border border-[rgba(212,160,57,0.28)] dark:bg-[var(--nous-ember)] dark:text-[var(--nous-helios)] dark:border-[rgba(232,184,74,0.22)]',
        success:
          'bg-emerald-400/[0.12] text-[#1a8a5e] border border-emerald-400/30 dark:text-emerald-300',
        danger:
          'bg-red-500/10 text-[#c93434] border border-red-500/[0.28] dark:text-red-300',
        muted:
          'bg-[var(--nous-bg-2)] text-[var(--nous-fg-3)] border border-[var(--nous-border-1)] dark:bg-[var(--nous-obsidian)] dark:border-[var(--nous-shade)]',
      },
    },
    defaultVariants: { variant: 'default' },
  }
);

interface StatusPillProps
  extends
    React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof statusPillVariants> {
  live?: boolean;
}

const StatusPill = React.forwardRef<HTMLSpanElement, StatusPillProps>(
  ({ className, variant, live, children, ...props }, ref) => (
    <span
      ref={ref}
      className={cn(statusPillVariants({ variant }), className)}
      {...props}
    >
      {live && (
        <span
          className="h-1.5 w-1.5 rounded-full bg-current"
          style={{ animation: 'nous-notif-ping 1.8s ease-in-out infinite' }}
        />
      )}
      {children}
    </span>
  )
);
StatusPill.displayName = 'StatusPill';

/* ─── Channel tag: typed identifier ─── */

interface ChannelTagProps extends React.HTMLAttributes<HTMLSpanElement> {
  channel: NotificationChannel;
  icon?: React.ReactNode;
}

const channelLabels: Record<NotificationChannel, string> = {
  document: 'Document',
  agent: 'Agent',
  system: 'System',
  collab: 'Collab',
  security: 'Security',
};

const ChannelTag = React.forwardRef<HTMLSpanElement, ChannelTagProps>(
  ({ className, channel, icon, children, ...props }, ref) => (
    <span
      ref={ref}
      data-notif-type={channel}
      className={cn(
        'inline-flex items-center gap-[5px]',
        'px-[7px] py-0.5',
        'rounded-[var(--nous-radius-sm)]',
        'font-[family-name:var(--nous-font-mono)] text-[9.5px] tracking-[0.1em] uppercase font-medium',
        'bg-[var(--type-bg)] text-[var(--type-fg)] border border-[var(--type-border)]',
        className
      )}
      {...props}
    >
      {icon && <span className="[&_svg]:h-2.5 [&_svg]:w-2.5">{icon}</span>}
      {children || channelLabels[channel]}
    </span>
  )
);
ChannelTag.displayName = 'ChannelTag';

/* ─── Presence avatar: initials + status dot ─── */

interface PresenceAvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  initials: string;
  gradient?: string;
}

const PresenceAvatar = React.forwardRef<HTMLDivElement, PresenceAvatarProps>(
  ({ className, initials, gradient, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'relative inline-flex items-center justify-center',
        'h-8 w-8 rounded-full text-white',
        'font-[family-name:var(--nous-font-ui)] text-[11px] font-semibold',
        className
      )}
      style={{
        background:
          gradient ||
          'linear-gradient(135deg, var(--nous-sol), var(--nous-helios))',
      }}
      {...props}
    >
      {initials}
      <span
        className={cn(
          'absolute -bottom-px -right-px',
          'h-2.5 w-2.5 rounded-full',
          'bg-[var(--nous-terra)]',
          'shadow-[0_0_0_2px_var(--nous-bg-2)]',
          'dark:shadow-[0_0_0_2px_var(--nous-obsidian)]'
        )}
      />
    </div>
  )
);
PresenceAvatar.displayName = 'PresenceAvatar';

export { DotBadge, CountBadge, StatusPill, ChannelTag, PresenceAvatar };
export { statusPillVariants };
