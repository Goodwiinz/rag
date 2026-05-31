import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';
import React from 'react';

export const ToggleSwitch: React.FC<{
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: string;
}> = ({ checked, onCheckedChange, label }) => (
  <button
    type="button"
    role="switch"
    aria-checked={checked}
    aria-label={label}
    onClick={() => onCheckedChange(!checked)}
    className={cn(
      'group flex w-full items-center justify-between rounded-lg border px-3 py-2 text-xs font-medium transition-colors',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
      checked
        ? 'border-primary/50 bg-primary/10 text-foreground'
        : 'border-border bg-muted/30 text-muted-foreground hover:border-[var(--nous-helios)]/50 hover:text-foreground'
    )}
  >
    <span className="truncate pr-3 text-left">{label}</span>
    <span
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 rounded-full border transition-colors',
        checked ? 'border-primary/60 bg-primary/20' : 'border-border bg-muted'
      )}
      aria-hidden="true"
    >
      <span
        className={cn(
          'mt-[2px] ml-[2px] block h-3.5 w-3.5 rounded-full transition-transform duration-200',
          checked
            ? 'translate-x-4 bg-primary'
            : 'translate-x-0 bg-muted-foreground'
        )}
      />
    </span>
  </button>
);

export const ProgressBar: React.FC<{ value: number; label?: string }> = ({
  value,
  label,
}) => (
  <div className="w-full space-y-1.5">
    {label && (
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span className="font-medium text-foreground tabular-nums">
          {Math.round(value)}%
        </span>
      </div>
    )}
    <div
      className="h-1.5 w-full overflow-hidden rounded-full bg-border"
      role="progressbar"
      aria-valuenow={Math.round(value)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label ?? 'Progress'}
    >
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${value}%` }}
        transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
        className="h-full rounded-full bg-primary"
      />
    </div>
  </div>
);

export const CustomSlider: React.FC<{
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step: number;
  label: string;
}> = ({ value, onChange, min, max, step, label }) => (
  <div className="space-y-3">
    <div className="flex items-center justify-between">
      <label className="text-xs font-medium text-muted-foreground">
        {label}
      </label>
      <span className="rounded-md border border-primary/20 bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary tabular-nums">
        {value}
      </span>
    </div>
    <input
      type="range"
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      min={min}
      max={max}
      step={step}
      aria-label={label}
      className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-border accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    />
  </div>
);
