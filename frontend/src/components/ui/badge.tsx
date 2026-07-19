import React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

// NOUS migration (2026-04-19):
//   - Handoff badges: px-3 py-1 font-medium gap-1.5 (softer than the old
//     px-2.5 py-0.5 font-semibold). Tightened sizing + weight here.
//   - New `accent` variant = Sol gold + white (handoff "Featured").
//   - New `muted` variant = Aurum parchment + Sol-safe (handoff "Draft").
const badgeVariants = cva(
  // gap-1.5 intentionally omitted from the base to avoid double-spacing with
  // existing call sites that already apply mr-1/ml-1 on icons. NOUS variants
  // that expect built-in icon spacing should use gap utility at the call site.
  'inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default:
          'border-transparent bg-primary text-primary-foreground hover:bg-primary/80',
        secondary:
          'border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80',
        destructive:
          'border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80',
        outline: 'text-foreground',
        success:
          'border-transparent bg-[var(--nous-terra)]/15 text-[var(--nous-terra)]',
        warning:
          'border-transparent bg-[var(--nous-corona)]/15 text-[var(--nous-corona)]',
        info: 'border-transparent bg-muted text-muted-foreground',
        accent:
          'border-transparent bg-[var(--nous-sol)] text-white hover:bg-[var(--nous-helios)]',
        muted:
          'border-transparent bg-[var(--nous-aurum)] text-[var(--nous-sol-safe)]',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

export interface BadgeProps
  extends
    React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

const Badge = React.forwardRef<HTMLDivElement, BadgeProps>(
  ({ className, variant, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  )
);

Badge.displayName = 'Badge';

export { Badge, badgeVariants };
