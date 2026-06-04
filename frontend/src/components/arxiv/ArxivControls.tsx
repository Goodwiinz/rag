'use client';

import { cn } from '@/lib/utils';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { motion } from 'framer-motion';
import React, { useId } from 'react';

export const ToggleSwitch: React.FC<{
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: string;
}> = ({ checked, onCheckedChange, label }) => {
  const labelId = useId();

  return (
    <label
      htmlFor={labelId}
      className={cn(
        'flex w-full cursor-pointer items-center justify-between gap-3 rounded-lg border px-3 py-2.5 text-sm transition-colors',
        checked
          ? 'border-primary/40 bg-primary/5 text-foreground'
          : 'border-border bg-card text-muted-foreground hover:border-border hover:text-foreground'
      )}
    >
      <span className="truncate text-left">{label}</span>
      <Switch
        id={labelId}
        checked={checked}
        onCheckedChange={onCheckedChange}
        aria-label={label}
        className="shrink-0"
      />
    </label>
  );
};

export const ProgressBar: React.FC<{ value: number; label?: string }> = ({
  value,
  label,
}) => (
  <div className="w-full space-y-1.5">
    {label && (
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span className="font-medium tabular-nums text-foreground">
          {Math.round(value)}%
        </span>
      </div>
    )}
    <div
      className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
      role="progressbar"
      aria-valuenow={Math.round(value)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${value}%` }}
        transition={{ duration: 0.35, ease: 'easeOut' }}
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
      <span className="text-sm font-medium text-foreground">{label}</span>
      <span className="rounded-md border border-border bg-card px-2 py-0.5 text-sm font-medium tabular-nums text-foreground">
        {value}
      </span>
    </div>
    <Slider
      value={[value]}
      onValueChange={(values) => onChange(values[0] ?? value)}
      min={min}
      max={max}
      step={step}
      aria-label={label}
    />
  </div>
);
