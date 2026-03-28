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
      'group flex w-full items-center justify-between rounded-lg border px-2.5 py-2 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors touch-manipulation',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D4A039]/60 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0A0A0A]',
      checked
        ? 'border-[#D4A039]/50 bg-[#D4A039]/10 text-[#E5E7EB]'
        : 'border-[#1A1A1A] bg-[#0A0A0A]/40 text-[#9CA3AF] hover:border-[#333333]'
    )}
  >
    <span className="truncate pr-3 text-left">{label}</span>
    <span
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 rounded-full border transition-colors',
        checked
          ? 'border-[#D4A039]/60 bg-[#D4A039]/20'
          : 'border-[#1A1A1A] bg-[#111111]'
      )}
      aria-hidden="true"
    >
      <span
        className={cn(
          'mt-[2px] ml-[2px] block h-3.5 w-3.5 rounded-full transition-transform',
          checked
            ? 'translate-x-4 bg-[#D4A039] shadow-[0_0_8px_rgba(212,160,57,0.65)]'
            : 'translate-x-0 bg-[#6B7280]'
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
      <div className="flex items-center justify-between text-[9px] font-mono uppercase tracking-widest text-[#6B7280]">
        <span>{label}</span>
        <span className="font-bold text-[#D4A039]">{Math.round(value)}%</span>
      </div>
    )}
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#1A1A1A]">
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${value}%` }}
        transition={{ duration: 0.35, ease: 'easeOut' }}
        className="h-full rounded-full bg-gradient-to-r from-[#B8882F] to-[#D4A039] shadow-[0_0_10px_rgba(212,160,57,0.35)]"
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
      <label className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#6B7280]">
        {label}
      </label>
      <span className="rounded border border-[#D4A039]/20 bg-[#D4A039]/10 px-2 py-0.5 text-[10px] font-mono font-bold text-[#D4A039]">
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
      className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-[#1A1A1A] accent-[#D4A039]"
    />
  </div>
);
