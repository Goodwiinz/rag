import * as React from 'react';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { NotificationChannel } from './types';

/* ─── 3a · Parchment banner ─── */

interface ParchmentBannerProps extends React.HTMLAttributes<HTMLDivElement> {
  channel: NotificationChannel;
  icon: React.ReactNode;
  title: string;
  description: React.ReactNode;
  ctaLabel?: string;
  onCtaClick?: () => void;
  onDismiss?: () => void;
}

const ParchmentBanner = React.forwardRef<HTMLDivElement, ParchmentBannerProps>(
  (
    {
      className,
      channel,
      icon,
      title,
      description,
      ctaLabel,
      onCtaClick,
      onDismiss,
      ...props
    },
    ref
  ) => (
    <div
      ref={ref}
      data-notif-type={channel}
      role="alert"
      aria-live="polite"
      className={cn(
        'relative grid grid-cols-[auto_1fr_auto_auto] items-start',
        'gap-3 py-3.5 pl-5 pr-3.5',
        'bg-[var(--nous-bg-3)] border border-[var(--nous-border-1)]',
        'border-l-[3px] border-l-[var(--type-marker,var(--nous-sol))]',
        'rounded-[var(--nous-radius-md)]',
        'group',
        className
      )}
      {...props}
    >
      {/* Icon */}
      <span
        className={cn(
          'mt-px shrink-0',
          'text-[var(--type-marker,var(--nous-sol))]',
          '[&_svg]:h-6 [&_svg]:w-6'
        )}
      >
        {icon}
      </span>

      {/* Body */}
      <div className="min-w-0">
        <span className="block font-[family-name:var(--nous-font-heading)] text-[14px] font-semibold tracking-[-0.005em] text-[var(--nous-fg-1)]">
          {title}
        </span>
        <div className="mt-0.5 font-[family-name:var(--nous-font-body)] text-[13.5px] leading-[1.5] text-[var(--nous-fg-2)] [&_code]:font-[family-name:var(--nous-font-mono)] [&_code]:text-[0.85em] [&_code]:px-[5px] [&_code]:py-px [&_code]:bg-[var(--nous-aurum)] [&_code]:text-[var(--nous-sol-safe)] [&_code]:rounded-[var(--nous-radius-sm)] dark:[&_code]:bg-[var(--nous-ember)] dark:[&_code]:text-[var(--nous-helios)]">
          {description}
        </div>
      </div>

      {/* CTA */}
      {ctaLabel && onCtaClick && (
        <button
          type="button"
          onClick={onCtaClick}
          className={cn(
            'inline-flex items-center shrink-0 self-center',
            'px-3 py-[7px]',
            'bg-[var(--nous-erebus)] text-[var(--nous-selene)]',
            'dark:bg-[var(--nous-sol)] dark:text-[var(--nous-erebus)]',
            'rounded-[var(--nous-radius-md)]',
            'font-[family-name:var(--nous-font-ui)] text-xs font-medium',
            'transition-all duration-150',
            'hover:-translate-y-px hover:shadow-[var(--nous-shadow-md)]'
          )}
        >
          {ctaLabel}
        </button>
      )}

      {/* Dismiss */}
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss banner"
          className={cn(
            'grid place-items-center shrink-0 self-start',
            'h-6 w-6',
            'rounded-[var(--nous-radius-sm)]',
            'text-[var(--nous-fg-3)]',
            'transition-all duration-150',
            'hover:bg-[var(--nous-bg-2)] hover:text-[var(--nous-fg-1)]'
          )}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  )
);
ParchmentBanner.displayName = 'ParchmentBanner';

/* ─── 3b · Manifesto banner ─── */

interface ManifestoBannerProps extends Omit<
  React.HTMLAttributes<HTMLDivElement>,
  'title'
> {
  eyebrow: string;
  title: React.ReactNode;
  description: React.ReactNode;
  ctaLabel: string;
  onCtaClick: () => void;
  linkLabel?: string;
  onLinkClick?: () => void;
}

const ManifestoBanner = React.forwardRef<HTMLDivElement, ManifestoBannerProps>(
  (
    {
      className,
      eyebrow,
      title,
      description,
      ctaLabel,
      onCtaClick,
      linkLabel,
      onLinkClick,
      ...props
    },
    ref
  ) => (
    <div
      ref={ref}
      role="alert"
      aria-live="polite"
      className={cn(
        'relative overflow-hidden',
        'grid grid-cols-1 sm:grid-cols-[1fr_auto] items-center',
        'gap-6 py-8 px-8',
        'bg-[var(--nous-erebus)] text-[var(--nous-selene)]',
        'rounded-[var(--nous-radius-lg)]',
        className
      )}
      {...props}
    >
      {/* Radial gold glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-12 -right-12 h-64 w-64"
        style={{
          background:
            'radial-gradient(circle, rgba(212,160,57,0.12) 0%, transparent 70%)',
        }}
      />

      {/* Body */}
      <div className="relative min-w-0">
        {/* Eyebrow */}
        <div className="mb-2 flex items-center gap-2">
          <span
            aria-hidden="true"
            className="inline-block h-px w-4 bg-[var(--nous-helios)]"
          />
          <span className="font-[family-name:var(--nous-font-mono)] text-[10px] uppercase tracking-[0.16em] text-[var(--nous-helios)]">
            {eyebrow}
          </span>
        </div>

        {/* Title */}
        <h3 className="mb-1.5 font-[family-name:var(--nous-font-heading)] text-[18px] font-semibold leading-[1.3] tracking-[-0.01em] text-[var(--nous-ivory)] [&_em]:font-[family-name:var(--nous-font-body)] [&_em]:italic [&_em]:font-normal [&_em]:text-[var(--nous-helios)]">
          {title}
        </h3>

        {/* Description */}
        <p className="font-[family-name:var(--nous-font-body)] text-[14px] leading-[1.55] text-[var(--nous-parchment)] max-w-[60ch]">
          {description}
        </p>
      </div>

      {/* Actions */}
      <div className="relative flex items-center gap-4 shrink-0">
        {linkLabel && onLinkClick && (
          <button
            type="button"
            onClick={onLinkClick}
            className={cn(
              'font-[family-name:var(--nous-font-ui)] text-sm font-medium',
              'text-[var(--nous-parchment)]',
              'transition-colors duration-150',
              'hover:text-[var(--nous-ivory)]',
              'underline underline-offset-2 decoration-[var(--nous-parchment)]/40',
              'hover:decoration-[var(--nous-ivory)]/60'
            )}
          >
            {linkLabel}
          </button>
        )}

        <button
          type="button"
          onClick={onCtaClick}
          className={cn(
            'inline-flex items-center shrink-0',
            'px-4 py-[9px]',
            'bg-[var(--nous-sol)] text-[var(--nous-erebus)]',
            'rounded-[var(--nous-radius-md)]',
            'font-[family-name:var(--nous-font-ui)] text-sm font-semibold',
            'transition-all duration-150',
            'hover:-translate-y-px hover:shadow-[0_4px_16px_rgba(212,160,57,0.3)]'
          )}
        >
          {ctaLabel}
        </button>
      </div>
    </div>
  )
);
ManifestoBanner.displayName = 'ManifestoBanner';

/* ─── 3c · Topbar banner ─── */

interface TopbarBannerProps extends React.HTMLAttributes<HTMLDivElement> {
  channel: NotificationChannel;
  tagLabel: string;
  tagIcon?: React.ReactNode;
  message: React.ReactNode;
  meta?: string;
  onDismiss?: () => void;
}

const TopbarBanner = React.forwardRef<HTMLDivElement, TopbarBannerProps>(
  (
    {
      className,
      channel,
      tagLabel,
      tagIcon,
      message,
      meta,
      onDismiss,
      ...props
    },
    ref
  ) => (
    <div
      ref={ref}
      data-notif-type={channel}
      role="alert"
      aria-live="polite"
      className={cn(
        'flex items-center gap-3',
        'py-2 px-3',
        'bg-[var(--nous-bg-2)] border border-[var(--nous-border-1)]',
        'rounded-[var(--nous-radius-md)]',
        className
      )}
      {...props}
    >
      {/* Tag */}
      <span
        className={cn(
          'inline-flex items-center gap-[5px] shrink-0',
          'px-[7px] py-0.5',
          'rounded-[var(--nous-radius-sm)]',
          'font-[family-name:var(--nous-font-mono)] text-[9.5px] tracking-[0.1em] uppercase font-medium',
          'bg-[var(--type-bg)] text-[var(--type-fg)] border border-[var(--type-border)]'
        )}
      >
        {tagIcon && (
          <span className="[&_svg]:h-2.5 [&_svg]:w-2.5">{tagIcon}</span>
        )}
        {tagLabel}
      </span>

      {/* Message */}
      <span className="flex-1 min-w-0 truncate font-[family-name:var(--nous-font-body)] text-[14px] text-[var(--nous-fg-1)] [&_strong]:font-[family-name:var(--nous-font-heading)] [&_strong]:font-semibold [&_a]:text-[var(--nous-sol-safe)] [&_a]:underline [&_a]:underline-offset-2 dark:[&_a]:text-[var(--nous-helios)]">
        {message}
      </span>

      {/* Meta */}
      {meta && (
        <span className="shrink-0 font-[family-name:var(--nous-font-mono)] text-[10px] tracking-[0.05em] text-[var(--nous-fg-3)]">
          {meta}
        </span>
      )}

      {/* Dismiss */}
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss banner"
          className={cn(
            'grid place-items-center shrink-0',
            'h-6 w-6',
            'rounded-[var(--nous-radius-sm)]',
            'text-[var(--nous-fg-3)]',
            'transition-all duration-150',
            'hover:bg-[var(--nous-bg-3)] hover:text-[var(--nous-fg-1)]'
          )}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  )
);
TopbarBanner.displayName = 'TopbarBanner';

export { ParchmentBanner, ManifestoBanner, TopbarBanner };
