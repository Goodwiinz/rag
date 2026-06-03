import React, { memo, useState } from 'react';
import { cn } from '@/lib/utils';

interface ErrorDisplayProps {
  error: string;
  onRetry?: () => void;
  onErrorClick?: () => void;
  retryCount?: number;
  canRetry?: boolean;
  compact?: boolean;
  showDetails?: boolean;
  maxRetryAttempts?: number;
  className?: string;
}

interface ErrorSeverity {
  type: 'warning' | 'error' | 'critical';
  icon: string;
  color: string;
  bgColor: string;
  borderColor: string;
  message: string;
}

// Determine error severity based on error message
const getErrorSeverity = (
  error: string,
  retryCount: number = 0
): ErrorSeverity => {
  const lowerError = error.toLowerCase();

  // Network/connection errors
  if (
    lowerError.includes('network') ||
    lowerError.includes('connection') ||
    lowerError.includes('timeout')
  ) {
    return {
      type: 'warning',
      icon: '⚠️',
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-50',
      borderColor: 'border-yellow-200',
      message: 'Connection issue - retrying may resolve this',
    };
  }

  // File format errors
  if (
    lowerError.includes('format') ||
    lowerError.includes('invalid') ||
    lowerError.includes('corrupt')
  ) {
    return {
      type: 'error',
      icon: '❌',
      color: 'text-red-600',
      bgColor: 'bg-red-50',
      borderColor: 'border-red-200',
      message: 'File format error - check file format',
    };
  }

  // Processing errors
  if (
    lowerError.includes('processing') ||
    lowerError.includes('extraction') ||
    lowerError.includes('ocr')
  ) {
    return {
      type: 'error',
      icon: '⚙️',
      color: 'text-red-600',
      bgColor: 'bg-red-50',
      borderColor: 'border-red-200',
      message: 'Processing error - check file content',
    };
  }

  // Critical system errors
  if (
    lowerError.includes('system') ||
    lowerError.includes('memory') ||
    lowerError.includes('disk')
  ) {
    return {
      type: 'critical',
      icon: '🚨',
      color: 'text-red-800',
      bgColor: 'bg-red-100',
      borderColor: 'border-red-300',
      message: 'System error - contact support',
    };
  }

  // Too many retries
  if (retryCount >= 3) {
    return {
      type: 'critical',
      icon: '🚫',
      color: 'text-red-800',
      bgColor: 'bg-red-100',
      borderColor: 'border-red-300',
      message: 'Maximum retry attempts reached',
    };
  }

  // Default error
  return {
    type: 'error',
    icon: '❌',
    color: 'text-red-600',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
    message: 'An error occurred',
  };
};

// Truncate error message for display
const truncateError = (error: string, maxLength: number = 100): string => {
  if (error.length <= maxLength) return error;
  return error.substring(0, maxLength) + '...';
};

export const ErrorDisplay: React.FC<ErrorDisplayProps> = memo(
  ({
    error,
    onRetry,
    onErrorClick,
    retryCount = 0,
    canRetry = true,
    compact = false,
    showDetails = false,
    maxRetryAttempts = 3,
    className = '',
  }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const severity = getErrorSeverity(error, retryCount);

    const handleRetry = (e: React.MouseEvent) => {
      e.stopPropagation();
      onRetry?.();
    };

    const handleErrorClick = (e: React.MouseEvent) => {
      e.stopPropagation();
      if (showDetails) {
        setIsExpanded(!isExpanded);
      }
      onErrorClick?.();
    };

    const isMaxRetriesReached = retryCount >= maxRetryAttempts;
    const shouldShowRetry = canRetry && !isMaxRetriesReached && onRetry;

    if (compact) {
      return (
        <div
          className={cn(
            'flex items-center justify-between p-2 rounded-md border',
            severity.bgColor,
            severity.borderColor,
            className
          )}
        >
          <div className="flex items-center space-x-2 min-w-0 flex-1">
            <span className="text-sm" role="img" aria-label="Error">
              {severity.icon}
            </span>
            <span className={cn('text-sm font-medium', severity.color)}>
              {severity.message}
            </span>
            {retryCount > 0 && (
              <span className="text-xs text-muted-foreground">
                (Retry #{retryCount})
              </span>
            )}
          </div>

          {shouldShowRetry && (
            <button
              onClick={handleRetry}
              className="px-3 py-1 text-xs font-medium text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded transition-colors"
              aria-label="Retry processing"
            >
              Retry
            </button>
          )}
        </div>
      );
    }

    return (
      <div
        className={cn(
          'rounded-lg border p-4',
          severity.bgColor,
          severity.borderColor,
          className
        )}
        role="alert"
        aria-live="polite"
      >
        {/* Header */}
        <div className="flex items-start justify-between mb-2">
          <div className="flex items-center space-x-2 min-w-0 flex-1">
            <span
              className="text-lg"
              role="img"
              aria-label={`${severity.type} error`}
            >
              {severity.icon}
            </span>
            <div className="min-w-0 flex-1">
              <h4 className={cn('text-sm font-medium', severity.color)}>
                {severity.message}
              </h4>
              {retryCount > 0 && (
                <p className="text-xs text-muted-foreground mt-1">
                  Retry attempt {retryCount} of {maxRetryAttempts}
                </p>
              )}
            </div>
          </div>

          {/* Retry Button */}
          {shouldShowRetry && (
            <button
              onClick={handleRetry}
              className="px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-md transition-colors flex items-center space-x-1"
              aria-label="Retry processing"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
              <span>Retry</span>
            </button>
          )}
        </div>

        {/* Error Message */}
        <div className="space-y-2">
          <div
            className={cn(
              'text-sm',
              severity.color,
              'cursor-pointer hover:underline',
              showDetails && 'select-all'
            )}
            onClick={handleErrorClick}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && handleErrorClick(e as any)}
            aria-label={
              showDetails
                ? isExpanded
                  ? 'Show less error details'
                  : 'Show full error details'
                : 'View error details'
            }
          >
            {isExpanded || !showDetails ? error : truncateError(error)}
            {showDetails && !isExpanded && (
              <span className="text-xs ml-1">Show more...</span>
            )}
          </div>

          {/* Expand/Collapse Button */}
          {showDetails && error.length > 100 && (
            <button
              onClick={handleErrorClick}
              className="text-xs text-blue-600 hover:text-blue-800 hover:underline"
              aria-label={
                isExpanded
                  ? 'Show less error details'
                  : 'Show more error details'
              }
            >
              {isExpanded ? 'Show less' : 'Show more'}
            </button>
          )}

          {/* Additional Information */}
          {severity.type === 'warning' && (
            <div className="text-xs text-foreground bg-white/50 rounded p-2">
              <p>
                💡 <strong>Suggestion:</strong> This error may resolve itself.
                Wait a moment and try again, or check your internet connection.
              </p>
            </div>
          )}

          {severity.type === 'critical' && (
            <div className="text-xs text-red-700 bg-red-50 rounded p-2 border border-red-200">
              <p>
                🆘 <strong>Support Needed:</strong> This error requires
                attention. Please contact support with the error details above.
              </p>
            </div>
          )}

          {isMaxRetriesReached && (
            <div className="text-xs text-orange-700 bg-orange-50 rounded p-2 border border-orange-200">
              <p>
                ⚠️ <strong>Max Retries:</strong> Maximum retry attempts (
                {maxRetryAttempts}) reached. The document requires manual
                intervention.
              </p>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="mt-4 pt-3 border-t border-border/50 flex items-center justify-between">
          <div className="flex items-center space-x-4 text-xs text-muted-foreground">
            <span>
              Error ID: {Math.random().toString(36).substr(2, 9).toUpperCase()}
            </span>
            <span>Time: {new Date().toLocaleTimeString()}</span>
          </div>

          {onErrorClick && !showDetails && (
            <button
              onClick={onErrorClick}
              className="text-xs text-blue-600 hover:text-blue-800 hover:underline"
              aria-label="View error details"
            >
              View Details
            </button>
          )}
        </div>
      </div>
    );
  }
);

ErrorDisplay.displayName = 'ErrorDisplay';
