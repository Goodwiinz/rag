import React, { memo, useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';

interface ProcessingProgressBarProps {
  progress: number; // 0-100
  size?: 'sm' | 'md' | 'lg';
  color?: string;
  backgroundColor?: string;
  showPercentage?: boolean;
  showLabel?: boolean;
  label?: string;
  animated?: boolean;
  striped?: boolean;
  indeterminate?: boolean;
  height?: number;
  className?: string;
  'aria-label'?: string;
  'aria-valuenow'?: number;
  'aria-valuemin'?: number;
  'aria-valuemax'?: number;
}

interface ProgressTheme {
  height: string;
  fontSize: string;
  borderRadius: string;
}

const PROGRESS_SIZES: Record<ProcessingProgressBarProps['size'], ProgressTheme> = {
  sm: {
    height: 'h-1',
    fontSize: 'text-xs',
    borderRadius: 'rounded-sm',
  },
  md: {
    height: 'h-2',
    fontSize: 'text-sm',
    borderRadius: 'rounded',
  },
  lg: {
    height: 'h-3',
    fontSize: 'text-base',
    borderRadius: 'rounded-md',
  },
};

const DEFAULT_COLORS = {
  primary: 'bg-blue-600',
  success: 'bg-green-600',
  warning: 'bg-yellow-600',
  error: 'bg-red-600',
  info: 'bg-cyan-600',
  gray: 'bg-gray-600',
};

// Helper to get progress color based on percentage
const getProgressColor = (progress: number): string => {
  if (progress >= 100) return DEFAULT_COLORS.success;
  if (progress >= 75) return DEFAULT_COLORS.primary;
  if (progress >= 50) return DEFAULT_COLORS.info;
  if (progress >= 25) return DEFAULT_COLORS.warning;
  return DEFAULT_COLORS.error;
};

// Helper to format progress percentage
const formatProgress = (progress: number): string => {
  return `${Math.round(progress)}%`;
};

export const ProcessingProgressBar: React.FC<ProcessingProgressBarProps> = memo(({
  progress,
  size = 'md',
  color,
  backgroundColor = 'bg-gray-200',
  showPercentage = true,
  showLabel = false,
  label,
  animated = true,
  striped = false,
  indeterminate = false,
  height,
  className = '',
  'aria-label': ariaLabel,
  'aria-valuenow': ariaValueNow,
  'aria-valuemin': ariaValueMin = 0,
  'aria-valuemax': ariaValueMax = 100,
}) => {
  const progressRef = useRef<HTMLDivElement>(null);
  const sizeTheme = PROGRESS_SIZES[size];
  const finalColor = color || getProgressColor(progress);

  // Clamp progress between 0 and 100
  const clampedProgress = Math.min(Math.max(progress, 0), 100);

  // Generate accessibility label
  const accessibilityLabel = ariaLabel || `${label || 'Progress'}: ${formatProgress(clampedProgress)}`;

  useEffect(() => {
    // Animate progress bar changes
    if (progressRef.current && animated) {
      progressRef.current.style.transition = 'transform 0.3s ease-out';
    }
  }, [clampedProgress, animated]);

  const containerClasses = cn(
    'relative overflow-hidden',
    height || sizeTheme.height,
    sizeTheme.borderRadius,
    backgroundColor,
    className
  );

  const indicatorClasses = cn(
    'absolute top-0 left-0 h-full transition-all duration-300 ease-out',
    finalColor,
    striped && 'bg-gradient-to-r from-transparent via-white/20 to-transparent',
    animated && striped && 'animate-pulse',
    indeterminate && 'animate-pulse'
  );

  const labelClasses = cn(
    'absolute inset-0 flex items-center justify-center text-xs font-medium',
    clampedProgress > 50 ? 'text-white' : 'text-gray-900',
    sizeTheme.fontSize
  );

  const indicatorStyle = {
    transform: `translateX(-${100 - clampedProgress}%)`,
  };

  if (indeterminate) {
    // Indeterminate progress bar (animated)
    return (
      <div
        className={containerClasses}
        role="progressbar"
        aria-label={accessibilityLabel}
        aria-valuemin={ariaValueMin}
        aria-valuemax={ariaValueMax}
      >
        <div
          ref={progressRef}
          className={cn(
            indicatorClasses,
            'w-1/3 animate-pulse'
          )}
          style={{
            transform: 'translateX(-100%)',
            animation: 'indeterminate-progress 1.5s ease-in-out infinite',
          }}
        />
        <style jsx>{`
          @keyframes indeterminate-progress {
            0% {
              transform: translateX(-100%);
            }
            50% {
              transform: translateX(200%);
            }
            100% {
              transform: translateX(-100%);
            }
          }
        `}</style>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* Label */}
      {(showLabel || label) && (
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">
            {label}
          </span>
          {showPercentage && (
            <span className="text-sm text-gray-500">
              {formatProgress(clampedProgress)}
            </span>
          )}
        </div>
      )}

      {/* Progress Bar */}
      <div
        className={containerClasses}
        role="progressbar"
        aria-label={accessibilityLabel}
        aria-valuenow={ariaValueNow ?? clampedProgress}
        aria-valuemin={ariaValueMin}
        aria-valuemax={ariaValueMax}
      >
        {/* Progress Indicator */}
        <div
          ref={progressRef}
          className={indicatorClasses}
          style={indicatorStyle}
        />

        {/* Percentage Text Overlay */}
        {showPercentage && (
          <div className={labelClasses}>
            {formatProgress(clampedProgress)}
          </div>
        )}
      </div>

      {/* Status Indicators */}
      {clampedProgress === 100 && (
        <div className="flex items-center justify-center">
          <svg
            className="w-5 h-5 text-green-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
          <span className="ml-1 text-sm text-green-600">Complete</span>
        </div>
      )}
    </div>
  );
});

ProcessingProgressBar.displayName = 'ProcessingProgressBar';