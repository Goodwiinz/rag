import * as React from 'react';
import { cn } from '@/lib/utils';
import type { NotificationChannel, NotificationAction } from './types';

/* ─── 4a · Block alert — filled tinted background ─── */

interface BlockAlertProps extends React.HTMLAttributes<HTMLDivElement> {
  channel: NotificationChannel;
  icon: React.ReactNode;
  title: string;
  description: React.ReactNode;
  actions?: NotificationAction[];
}

const BlockAlert = React.forwardRef<HTMLDivElement, BlockAlertProps>(
  (
    { className, channel, icon, title, description, actions, ...props },
    ref
  ) => (
    <div
      ref={ref}
      data-notif-type={channel}
      role="alert"
      className={cn(
        'grid grid-cols-[auto_1fr_auto] items-start',
        'gap-3.5 py-3.5 px-4',
        'bg-[var(--type-bg)] border border-[var(--type-border)]',
        'rounded-[var(--nous-radius-md)]',
        className
      )}
      {...props}
    >
      {/* Icon */}
      <span
        className={cn(
          'grid place-items-center shrink-0',
          'text-[var(--type-fg)]',
          '[&_svg]:h-6 [&_svg]:w-6'
        )}
      >
        {icon}
      </span>

      {/* Body */}
      <div className="min-w-0">
        <span className="font-[family-name:var(--nous-font-heading)] text-[14px] font-semibold tracking-[-0.005em] text-[var(--nous-fg-1)]">
          {title}
        </span>
        <div
          className={cn(
            'mt-1 font-[family-name:var(--nous-font-body)] text-[13.5px] leading-[1.55] text-[var(--nous-fg-2)]',
            '[&_ul]:mt-1.5 [&_ul]:pl-4 [&_ul]:text-[13px]',
            '[&_ul_li]:mb-0.5'
          )}
        >
          {description}
        </div>
      </div>

      {/* Actions */}
      {actions && actions.length > 0 && (
        <div className="flex gap-1.5 self-start">
          {actions.map((a) => (
            <button
              key={a.label}
              type="button"
              onClick={a.onClick}
              className={cn(
                'font-[family-name:var(--nous-font-ui)] text-xs font-medium',
                'px-2 py-1 rounded-[var(--nous-radius-sm)]',
                'text-[var(--type-fg)]',
                'transition-all duration-150',
                'hover:bg-black/[0.05] dark:hover:bg-white/[0.05]'
              )}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
);
BlockAlert.displayName = 'BlockAlert';

/* ─── 4b · Outline alert — subtle, low chrome ─── */

interface OutlineAlertProps extends React.HTMLAttributes<HTMLDivElement> {
  channel: NotificationChannel;
  icon: React.ReactNode;
  title: string;
  description: React.ReactNode;
  meta?: React.ReactNode;
  ctaLabel?: string;
  onCtaClick?: () => void;
}

const OutlineAlert = React.forwardRef<HTMLDivElement, OutlineAlertProps>(
  (
    {
      className,
      channel,
      icon,
      title,
      description,
      meta,
      ctaLabel,
      onCtaClick,
      ...props
    },
    ref
  ) => (
    <div
      ref={ref}
      data-notif-type={channel}
      role="alert"
      className={cn(
        'grid grid-cols-[4px_1fr_auto] items-start',
        'gap-0',
        'bg-[var(--nous-bg-2)] border border-[var(--nous-border-1)]',
        'rounded-[var(--nous-radius-md)] overflow-hidden',
        'dark:bg-[var(--nous-obsidian)] dark:border-[var(--nous-shade)]',
        className
      )}
      {...props}
    >
      {/* Marker bar */}
      <span className="w-1 self-stretch rounded-[2px] bg-[var(--type-marker)]" />

      {/* Body */}
      <div className="min-w-0 py-3 px-3.5">
        {/* Head: icon + title */}
        <div className="mb-1 flex items-center gap-2">
          <span
            className={cn(
              'shrink-0 text-[var(--type-marker)]',
              '[&_svg]:h-3.5 [&_svg]:w-3.5'
            )}
          >
            {icon}
          </span>
          <span className="font-[family-name:var(--nous-font-heading)] text-[13.5px] font-semibold text-[var(--nous-fg-1)]">
            {title}
          </span>
        </div>

        {/* Description */}
        <div className="font-[family-name:var(--nous-font-body)] text-[13.5px] leading-[1.55] text-[var(--nous-fg-2)]">
          {description}
        </div>

        {/* Meta */}
        {meta && (
          <div className="mt-1.5 flex items-center gap-3 font-[family-name:var(--nous-font-mono)] text-[10px] tracking-[0.05em] text-[var(--nous-fg-3)]">
            {meta}
          </div>
        )}
      </div>

      {/* CTA button */}
      {ctaLabel && onCtaClick && (
        <button
          type="button"
          onClick={onCtaClick}
          className={cn(
            'self-center mr-3.5',
            'font-[family-name:var(--nous-font-ui)] text-[12.5px] font-medium',
            'px-2.5 py-1.5',
            'border border-[var(--nous-border-1)]',
            'rounded-[var(--nous-radius-sm)]',
            'text-[var(--nous-fg-1)]',
            'transition-all duration-150',
            'hover:border-[var(--nous-sol-safe)] hover:bg-[var(--nous-bg-3)]',
            'dark:hover:border-[var(--nous-helios)]'
          )}
        >
          {ctaLabel}
        </button>
      )}
    </div>
  )
);
OutlineAlert.displayName = 'OutlineAlert';

/* ─── 4c · Quote alert — margin-note serif feel ─── */

interface QuoteAlertProps extends React.HTMLAttributes<HTMLDivElement> {
  channel: NotificationChannel;
  icon: React.ReactNode;
  headLabel: string;
  title: string;
  description: React.ReactNode;
  actionLabel?: string;
  onActionClick?: () => void;
  meta?: React.ReactNode;
}

const QuoteAlert = React.forwardRef<HTMLDivElement, QuoteAlertProps>(
  (
    {
      className,
      channel,
      icon,
      headLabel,
      title,
      description,
      actionLabel,
      onActionClick,
      meta,
      ...props
    },
    ref
  ) => (
    <div
      ref={ref}
      data-notif-type={channel}
      role="alert"
      className={cn(
        'relative border-l-2 border-l-[var(--type-marker)]',
        'bg-transparent',
        'pl-4 py-1',
        className
      )}
      {...props}
    >
      {/* Positioned dot */}
      <span
        className="absolute -left-[5px] top-1 h-2 w-2 rounded-full bg-[var(--type-marker)]"
        aria-hidden="true"
      />

      {/* Head: mono label + icon */}
      <div className="mb-1 flex items-center gap-1.5 font-[family-name:var(--nous-font-mono)] text-[10px] uppercase tracking-[0.12em] text-[var(--type-fg)]">
        <span className="[&_svg]:h-3 [&_svg]:w-3">{icon}</span>
        <span>{headLabel}</span>
      </div>

      {/* Title */}
      <div className="font-[family-name:var(--nous-font-heading)] text-[15px] font-semibold text-[var(--nous-fg-1)]">
        {title}
      </div>

      {/* Description */}
      <div
        className={cn(
          'mt-1 font-[family-name:var(--nous-font-body)] text-[14.5px] leading-[1.55] text-[var(--nous-fg-2)]',
          'max-w-[60ch]',
          '[&_em]:italic [&_em]:text-[var(--nous-fg-accent-safe)]'
        )}
      >
        {description}
      </div>

      {/* Foot: action link + meta */}
      {(actionLabel || meta) && (
        <div className="mt-2 flex items-center gap-3">
          {actionLabel && onActionClick && (
            <button
              type="button"
              onClick={onActionClick}
              className={cn(
                'font-[family-name:var(--nous-font-ui)] text-[12.5px] font-medium',
                'text-[var(--nous-sol-safe)] dark:text-[var(--nous-helios)]',
                'underline underline-offset-2',
                'transition-colors duration-150',
                'hover:text-[var(--nous-helios)] dark:hover:text-[var(--nous-apollo)]'
              )}
            >
              {actionLabel}
            </button>
          )}
          {meta && (
            <span className="font-[family-name:var(--nous-font-mono)] text-[10px] tracking-[0.05em] text-[var(--nous-fg-3)]">
              {meta}
            </span>
          )}
        </div>
      )}
    </div>
  )
);
QuoteAlert.displayName = 'QuoteAlert';

export { BlockAlert, OutlineAlert, QuoteAlert };
