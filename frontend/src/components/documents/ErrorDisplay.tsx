import React from 'react';
import {
  ExclamationTriangleIcon,
  XCircleIcon,
  InformationCircleIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';

export type ErrorSeverity = 'error' | 'warning' | 'info';
export type ErrorType = 'processing' | 'validation' | 'network' | 'authentication' | 'unknown';

export interface ErrorDisplayProps {
  /** Error message to display */
  error: string | Error;

  /** Error severity level (default: 'error') */
  severity?: ErrorSeverity;

  /** Error type for categorization */
  errorType?: ErrorType;

  /** Optional error title (auto-generated if not provided) */
  title?: string;

  /** Optional error details or stack trace */
  details?: string;

  /** Show error details in expandable section */
  showDetails?: boolean;

  /** Retry callback */
  onRetry?: () => void;

  /** Dismiss callback */
  onDismiss?: () => void;

  /** Additional custom actions */
  actions?: Array<{
    label: string;
    onClick: () => void;
    variant?: 'primary' | 'secondary' | 'destructive';
  }>;

  /** Enable compact mode for inline errors */
  compact?: boolean;

  /** Custom className */
  className?: string;

  /** Timestamp of when error occurred */
  timestamp?: Date;
}

const getErrorIcon = (severity: ErrorSeverity) => {
  const iconClass = "h-5 w-5 flex-shrink-0 mt-0.5";

  switch (severity) {
    case 'error':
      return <XCircleIcon className={cn(iconClass, "text-destructive")} />;
    case 'warning':
      return <ExclamationTriangleIcon className={cn(iconClass, "text-yellow-600")} />;
    case 'info':
      return <InformationCircleIcon className={cn(iconClass, "text-blue-600")} />;
    default:
      return <XCircleIcon className={cn(iconClass, "text-destructive")} />;
  }
};

const getDefaultTitle = (errorType: ErrorType, severity: ErrorSeverity): string => {
  if (severity === 'warning') {
    switch (errorType) {
      case 'processing': return 'Processing Warning';
      case 'validation': return 'Validation Warning';
      case 'network': return 'Connection Warning';
      case 'authentication': return 'Authentication Warning';
      default: return 'Warning';
    }
  }

  if (severity === 'info') {
    return 'Information';
  }

  switch (errorType) {
    case 'processing': return 'Processing Error';
    case 'validation': return 'Validation Error';
    case 'network': return 'Network Error';
    case 'authentication': return 'Authentication Error';
    default: return 'Error';
  }
};

const getContainerStyles = (severity: ErrorSeverity): string => {
  switch (severity) {
    case 'error':
      return 'bg-destructive/10 border-destructive/20';
    case 'warning':
      return 'bg-yellow-50 border-yellow-200';
    case 'info':
      return 'bg-blue-50 border-blue-200';
    default:
      return 'bg-destructive/10 border-destructive/20';
  }
};

const getTextStyles = (severity: ErrorSeverity): string => {
  switch (severity) {
    case 'error':
      return 'text-destructive';
    case 'warning':
      return 'text-yellow-800';
    case 'info':
      return 'text-blue-800';
    default:
      return 'text-destructive';
  }
};

const formatTimestamp = (timestamp: Date): string => {
  const now = new Date();
  const diffMs = now.getTime() - timestamp.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 5) return 'just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  return `${diffHours}h ago`;
};

/**
 * ErrorDisplay component for displaying errors with various severity levels
 *
 * @example
 * ```tsx
 * <ErrorDisplay
 *   error="Failed to process document"
 *   severity="error"
 *   errorType="processing"
 *   onRetry={handleRetry}
 *   onDismiss={handleDismiss}
 * />
 * ```
 */
export const ErrorDisplay: React.FC<ErrorDisplayProps> = ({
  error,
  severity = 'error',
  errorType = 'unknown',
  title,
  details,
  showDetails = false,
  onRetry,
  onDismiss,
  actions,
  compact = false,
  className,
  timestamp,
}) => {
  const [isExpanded, setIsExpanded] = React.useState(false);

  const errorMessage = error instanceof Error ? error.message : error;
  const errorDetails = details || (error instanceof Error ? error.stack : undefined);
  const errorTitle = title || getDefaultTitle(errorType, severity);

  if (compact) {
    return (
      <div className={cn(
        "flex items-center space-x-2 p-2 rounded-md border text-sm",
        getContainerStyles(severity),
        className
      )}>
        {getErrorIcon(severity)}
        <span className={cn("flex-1 truncate", getTextStyles(severity))}>
          {errorMessage}
        </span>
        {onRetry && (
          <button
            onClick={onRetry}
            className={cn(
              "text-xs px-2 py-1 rounded hover:bg-black/5 transition-colors",
              getTextStyles(severity)
            )}
          >
            Retry
          </button>
        )}
        {onDismiss && (
          <button
            onClick={onDismiss}
            className={cn(
              "p-1 rounded hover:bg-black/5 transition-colors",
              getTextStyles(severity)
            )}
            aria-label="Dismiss"
          >
            <XMarkIcon className="h-4 w-4" />
          </button>
        )}
      </div>
    );
  }

  return (
    <div className={cn(
      "p-4 rounded-md border",
      getContainerStyles(severity),
      className
    )}>
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-3 flex-1 min-w-0">
          {getErrorIcon(severity)}

          <div className={cn("flex-1 min-w-0", getTextStyles(severity))}>
            {/* Title and timestamp */}
            <div className="flex items-center justify-between mb-1">
              <p className="font-medium">{errorTitle}</p>
              {timestamp && (
                <span className="text-xs opacity-70 ml-2">
                  {formatTimestamp(timestamp)}
                </span>
              )}
            </div>

            {/* Error message */}
            <p className="text-sm mt-1 break-words">{errorMessage}</p>

            {/* Expandable details */}
            {errorDetails && showDetails && (
              <div className="mt-2">
                <button
                  onClick={() => setIsExpanded(!isExpanded)}
                  className="text-xs underline hover:no-underline"
                >
                  {isExpanded ? 'Hide' : 'Show'} details
                </button>

                {isExpanded && (
                  <pre className="mt-2 p-2 bg-black/5 rounded text-xs overflow-x-auto">
                    {errorDetails}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>

        {onDismiss && (
          <button
            onClick={onDismiss}
            className={cn(
              "p-1 rounded hover:bg-black/5 transition-colors ml-2",
              getTextStyles(severity)
            )}
            aria-label="Dismiss"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* Actions */}
      {(onRetry || actions) && (
        <div className="flex items-center space-x-2 mt-4 pt-3 border-t border-current/20">
          {onRetry && (
            <button
              onClick={onRetry}
              className={cn(
                "px-3 py-1.5 text-sm font-medium rounded hover:bg-black/10 transition-colors",
                getTextStyles(severity)
              )}
            >
              Retry
            </button>
          )}

          {actions?.map((action, index) => (
            <button
              key={index}
              onClick={action.onClick}
              className={cn(
                "px-3 py-1.5 text-sm font-medium rounded transition-colors",
                action.variant === 'primary' && "bg-primary text-primary-foreground hover:bg-primary/90",
                action.variant === 'secondary' && "hover:bg-black/10",
                action.variant === 'destructive' && "bg-destructive text-destructive-foreground hover:bg-destructive/90",
                !action.variant && "hover:bg-black/10",
                !action.variant && getTextStyles(severity)
              )}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default ErrorDisplay;
