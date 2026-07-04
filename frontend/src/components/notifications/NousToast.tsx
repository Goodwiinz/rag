import * as React from 'react';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { NotificationChannel, NotificationAction } from './types';
import { ChannelTag } from './NotificationBadge';

/* ─── 2a · Scholarly toast ─── */

interface ScholarlyToastProps extends React.HTMLAttributes<HTMLDivElement> {
  channel: NotificationChannel;
  icon: React.ReactNode;
  channelIcon?: React.ReactNode;
  title: string;
  snippet: React.ReactNode;
  meta?: React.ReactNode;
  actions?: NotificationAction[];
  onClose?: () => void;
  showProgress?: boolean;
  progressPercent?: number;
}

const ScholarlyToast = React.forwardRef<HTMLDivElement, ScholarlyToastProps>(
  (
    {
      className,
      channel,
      icon,
      channelIcon,
      title,
      snippet,
      meta,
      actions,
      onClose,
      showProgress,
      progressPercent = 35,
      ...props
    },
    ref
  ) => (
    <div
      ref={ref}
      data-notif-type={channel}
      role="status"
      aria-live="polite"
      className={cn(
        'relative grid grid-cols-[auto_1fr_auto] items-start',
        'gap-3.5 py-3.5 pl-[22px] pr-[18px]',
        'w-[380px]',
        'bg-(--nous-bg-2) border border-(--nous-border-1)',
        'rounded-(--nous-radius-lg)',
        'shadow-(--nous-shadow-lg)',
        'dark:bg-(--nous-obsidian) dark:border-(--nous-shade)',
        'group',
        className
      )}
      {...props}
    >
      {/* Gold marker rail */}
      <span className="absolute left-0 top-3.5 bottom-3.5 w-[3px] rounded-r-sm bg-(--type-marker,var(--nous-sol))" />

      {/* Icon */}
      <span
        className={cn(
          'grid place-items-center',
          'h-[30px] w-[30px] shrink-0',
          'rounded-(--nous-radius-md)',
          'bg-(--type-bg) text-(--type-fg)',
          'border border-(--type-border)',
          '[&_svg]:h-3.5 [&_svg]:w-3.5'
        )}
      >
        {icon}
      </span>

      {/* Body */}
      <div className="min-w-0">
        <div className="mb-1 flex flex-wrap items-center gap-2">
          <span className="font-(family-name:--nous-font-heading) text-[13.5px] font-semibold tracking-[-0.005em] text-(--nous-fg-1)">
            {title}
          </span>
          <ChannelTag channel={channel} icon={channelIcon} />
        </div>
        <div className="font-(family-name:--nous-font-body) text-sm leading-normal text-(--nous-fg-2) [&_code]:font-(family-name:--nous-font-mono) [&_code]:text-[0.85em] [&_code]:px-[5px] [&_code]:py-px [&_code]:bg-(--nous-aurum) [&_code]:text-(--nous-sol-safe) [&_code]:rounded-(--nous-radius-sm) dark:[&_code]:bg-(--nous-ember) dark:[&_code]:text-(--nous-helios)">
          {snippet}
        </div>
        {meta && (
          <div className="mt-1.5 flex items-center gap-3 font-(family-name:--nous-font-mono) text-[10px] tracking-wider text-(--nous-fg-3)">
            {meta}
          </div>
        )}
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
                'font-(family-name:--nous-font-ui) text-xs font-medium',
                'px-2 py-1 rounded-(--nous-radius-sm)',
                'transition-all duration-150',
                a.variant === 'primary'
                  ? 'text-(--nous-sol-safe) font-semibold dark:text-(--nous-helios)'
                  : 'text-(--nous-fg-3) hover:text-(--nous-fg-1) hover:bg-(--nous-aurum) dark:hover:bg-(--nous-dusk) dark:hover:text-(--nous-ivory)'
              )}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}

      {/* Close */}
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          aria-label="Dismiss notification"
          className={cn(
            'absolute top-2 right-2',
            'grid place-items-center h-[22px] w-[22px]',
            'rounded-(--nous-radius-sm)',
            'text-(--nous-fg-3)',
            'opacity-0 group-hover:opacity-100',
            'transition-all duration-150',
            'hover:bg-(--nous-bg-3) hover:text-(--nous-fg-1)'
          )}
        >
          <X className="h-3 w-3" />
        </button>
      )}

      {/* Progress sliver */}
      {showProgress && (
        <span className="absolute left-3 right-3 bottom-1 h-px rounded-[1px] bg-(--nous-border-1) overflow-hidden">
          <span
            className="block h-full rounded-[1px] bg-(--type-marker,var(--nous-sol))"
            style={{ width: `${progressPercent}%` }}
          />
        </span>
      )}
    </div>
  )
);
ScholarlyToast.displayName = 'ScholarlyToast';

/* ─── 2b · Mono toast ─── */

interface MonoToastProps extends React.HTMLAttributes<HTMLDivElement> {
  channel: NotificationChannel;
  icon: React.ReactNode;
  timestamp: string;
  typeLabel: string;
  severity?: string;
  line: React.ReactNode;
  actions?: NotificationAction[];
}

const MonoToast = React.forwardRef<HTMLDivElement, MonoToastProps>(
  (
    {
      className,
      channel,
      icon,
      timestamp,
      typeLabel,
      severity,
      line,
      actions,
      ...props
    },
    ref
  ) => (
    <div
      ref={ref}
      data-notif-type={channel}
      role="status"
      aria-live="polite"
      className={cn(
        'relative grid grid-cols-[auto_1fr_auto] items-start',
        'gap-3.5 py-3.5 px-[18px]',
        'w-[380px]',
        'bg-(--nous-erebus) text-(--nous-ivory)',
        'border border-white/6',
        'rounded-(--nous-radius-md)',
        'shadow-(--nous-shadow-lg)',
        'overflow-hidden',
        className
      )}
      {...props}
    >
      {/* Top accent line */}
      <span className="absolute top-0 left-0 right-0 h-px bg-linear-to-r from-transparent via-(--type-marker,var(--nous-sol)) to-transparent opacity-60" />

      {/* Glyph */}
      <span
        className={cn(
          'grid place-items-center',
          'h-[26px] w-[26px] shrink-0',
          'rounded-(--nous-radius-sm)',
          'bg-white/4 text-(--type-marker,var(--nous-helios))',
          'border border-(--type-border)',
          '[&_svg]:h-[13px] [&_svg]:w-[13px]'
        )}
      >
        {icon}
      </span>

      {/* Body */}
      <div className="min-w-0 font-(family-name:--nous-font-mono)">
        <div className="mb-1 flex items-center gap-2 text-[9.5px] uppercase tracking-[0.14em] text-(--nous-dust)">
          <span>{timestamp}</span>
          <span className="text-(--nous-clay)">&middot;</span>
          <span className="font-semibold text-(--type-marker)">
            {typeLabel}
          </span>
          {severity && (
            <>
              <span className="text-(--nous-clay)">&middot;</span>
              <span>{severity}</span>
            </>
          )}
        </div>
        <div className="text-[12.5px] leading-normal text-(--nous-ivory) [&_.key]:text-(--nous-dust) [&_.val]:text-(--nous-helios)">
          {line}
        </div>
      </div>

      {/* Actions */}
      {actions && actions.length > 0 && (
        <div className="flex flex-col items-end gap-1">
          {actions.map((a) => (
            <button
              key={a.label}
              type="button"
              onClick={a.onClick}
              className={cn(
                'font-(family-name:--nous-font-mono) text-[10px] uppercase tracking-widest',
                'px-2 py-[3px] rounded-(--nous-radius-sm)',
                'transition-all duration-150',
                a.variant === 'ghost'
                  ? 'text-(--nous-parchment) border-transparent hover:text-(--nous-ivory) hover:bg-white/4'
                  : 'text-(--nous-helios) border border-[rgba(232,184,74,0.25)] hover:bg-(--nous-ember)'
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
MonoToast.displayName = 'MonoToast';

/* ─── 2c · Headline toast ─── */

interface HeadlineToastProps extends React.HTMLAttributes<HTMLDivElement> {
  channel: NotificationChannel;
  art?: React.ReactNode;
  artType?: 'mark' | 'avatar';
  avatarInitials?: string;
  avatarGradient?: string;
  eyebrow: string;
  headline: React.ReactNode;
  ctaLabel: string;
  onCtaClick: () => void;
}

const HeadlineToast = React.forwardRef<HTMLDivElement, HeadlineToastProps>(
  (
    {
      className,
      channel,
      art,
      artType = 'mark',
      avatarInitials,
      avatarGradient,
      eyebrow,
      headline,
      ctaLabel,
      onCtaClick,
      ...props
    },
    ref
  ) => (
    <div
      ref={ref}
      data-notif-type={channel}
      role="status"
      aria-live="polite"
      className={cn(
        'relative grid grid-cols-[auto_1fr_auto] items-center',
        'gap-3.5 py-3.5 px-[18px]',
        'w-[420px]',
        'bg-(--nous-bg-2) border border-(--nous-border-1)',
        'rounded-(--nous-radius-xl)',
        'shadow-(--nous-shadow-lg)',
        'dark:bg-(--nous-obsidian) dark:border-(--nous-shade)',
        className
      )}
      {...props}
    >
      {/* Art medallion */}
      {artType === 'mark' ? (
        <div
          className={cn(
            'grid place-items-center',
            'h-11 w-11 shrink-0 rounded-full',
            'text-white font-(family-name:--nous-font-heading) font-semibold text-[13px]'
          )}
          style={{
            background: `radial-gradient(circle at 30% 30%, var(--type-marker, var(--nous-sol)) 0%, transparent 50%), radial-gradient(circle at 70% 70%, var(--type-marker, var(--nous-sol)) 0%, transparent 50%), var(--nous-erebus)`,
          }}
        >
          {art}
        </div>
      ) : (
        <div
          className={cn(
            'grid place-items-center',
            'h-11 w-11 shrink-0 rounded-full',
            'text-white font-(family-name:--nous-font-heading) font-semibold text-[13px]'
          )}
          style={{
            background:
              avatarGradient ||
              'linear-gradient(135deg, var(--nous-sol), var(--nous-helios))',
          }}
        >
          {avatarInitials || art}
        </div>
      )}

      {/* Body */}
      <div className="min-w-0">
        <div className="mb-0.5 font-(family-name:--nous-font-mono) text-[9.5px] uppercase tracking-[0.16em] text-(--type-fg,var(--nous-fg-accent-safe))">
          {eyebrow}
        </div>
        <div className="font-(family-name:--nous-font-heading) text-[15px] font-semibold tracking-[-0.01em] leading-[1.3] text-(--nous-fg-1) [&_em]:font-(family-name:--nous-font-body) [&_em]:italic [&_em]:font-normal [&_em]:text-(--nous-fg-accent-safe)">
          {headline}
        </div>
      </div>

      {/* CTA */}
      <button
        type="button"
        onClick={onCtaClick}
        className={cn(
          'inline-flex items-center gap-[5px] shrink-0',
          'px-3 py-[7px]',
          'bg-(--nous-erebus) text-(--nous-selene)',
          'dark:bg-(--nous-sol) dark:text-(--nous-erebus)',
          'rounded-(--nous-radius-md)',
          'font-(family-name:--nous-font-ui) text-xs font-medium',
          'transition-all duration-150',
          'hover:-translate-y-px hover:shadow-(--nous-shadow-md)',
          '[&_svg]:h-3 [&_svg]:w-3'
        )}
      >
        {ctaLabel}
      </button>
    </div>
  )
);
HeadlineToast.displayName = 'HeadlineToast';

export { ScholarlyToast, MonoToast, HeadlineToast };
