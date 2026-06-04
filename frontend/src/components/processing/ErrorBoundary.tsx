/**
 * Error Boundary Components
 *
 * React error boundaries for catching and handling errors in
 * the real-time processing components gracefully.
 */

import React, { Component, ErrorInfo, ReactNode } from 'react';
import {
  ExclamationTriangleIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  SignalIcon,
  ServerIcon,
} from '@heroicons/react/24/outline';

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
  errorId?: string;
  retryCount: number;
}

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo, errorId: string) => void;
  maxRetries?: number;
  component?: string;
  showErrorDetails?: boolean;
  enableRetry?: boolean;
}

interface FallbackUIProps {
  error: Error;
  errorInfo?: ErrorInfo;
  onRetry?: () => void;
  onDismiss?: () => void;
  retryCount?: number;
  maxRetries?: number;
  component?: string;
  showErrorDetails?: boolean;
  enableRetry?: boolean;
}

// Default fallback UI component
const FallbackUI: React.FC<FallbackUIProps> = ({
  error,
  errorInfo,
  onRetry,
  onDismiss,
  retryCount = 0,
  maxRetries = 3,
  component = 'Component',
  showErrorDetails = false,
  enableRetry = true,
}) => {
  const [showDetails, setShowDetails] = React.useState(false);

  const getErrorIcon = () => {
    if (
      error.name === 'ChunkLoadError' ||
      error.message.includes('Loading chunk')
    ) {
      return DocumentTextIcon;
    }
    if (
      error.message.includes('WebSocket') ||
      error.message.includes('connection')
    ) {
      return SignalIcon;
    }
    if (error.message.includes('Network') || error.message.includes('fetch')) {
      return ServerIcon;
    }
    return ExclamationTriangleIcon;
  };

  const Icon = getErrorIcon();

  const canRetry = enableRetry && retryCount < maxRetries;
  const isRetryableError =
    error.name === 'ChunkLoadError' ||
    error.message.includes('Loading chunk') ||
    error.message.includes('Network') ||
    error.message.includes('WebSocket');

  return (
    <div className="min-h-[200px] bg-background rounded-lg border border-[var(--nous-mars)]/40 p-6">
      <div className="flex items-start space-x-4">
        <div className="flex-shrink-0">
          <div className="p-2 bg-[var(--nous-mars)]/15 rounded-full">
            <Icon className="w-6 h-6 text-[var(--nous-mars)]" />
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-medium text-foreground mb-2">
            {component} Error
          </h3>

          <p className="text-sm text-foreground mb-4">
            Something went wrong while rendering this component. The error has
            been logged and our team will investigate.
          </p>

          {/* Error summary */}
          <div className="bg-[var(--nous-mars)]/10 border border-[var(--nous-mars)]/40 rounded p-3 mb-4">
            <p className="text-sm font-medium text-[var(--nous-mars)] mb-1">
              {error.name}: {error.message}
            </p>
            {component && (
              <p className="text-xs text-[var(--nous-mars)]">
                Component: {component}
              </p>
            )}
          </div>

          {/* Action buttons */}
          <div className="flex items-center space-x-3">
            {canRetry && isRetryableError && onRetry && (
              <button
                onClick={onRetry}
                className="inline-flex items-center px-3 py-2 text-sm font-medium text-[var(--nous-fg-accent-safe)] bg-[var(--nous-sol)]/15 hover:bg-[var(--nous-sol)]/25 rounded transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <ArrowPathIcon className="w-4 h-4 mr-2" />
                Retry {retryCount > 0 ? `(${retryCount}/${maxRetries})` : ''}
              </button>
            )}

            {showErrorDetails && (
              <button
                onClick={() => setShowDetails(!showDetails)}
                className="inline-flex items-center px-3 py-2 text-sm font-medium text-foreground bg-[var(--nous-bg-2)] hover:bg-[var(--nous-bg-3)] rounded transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                {showDetails ? 'Hide' : 'Show'} Details
              </button>
            )}

            {onDismiss && (
              <button
                onClick={onDismiss}
                className="inline-flex items-center px-3 py-2 text-sm font-medium text-foreground bg-[var(--nous-bg-2)] hover:bg-[var(--nous-bg-3)] rounded transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                Dismiss
              </button>
            )}
          </div>

          {/* Detailed error information */}
          {showDetails && showErrorDetails && (
            <div className="mt-4 space-y-3">
              <div className="bg-[var(--nous-bg-2)] border border-border rounded p-3">
                <h4 className="text-sm font-medium text-foreground mb-2">
                  Error Stack Trace
                </h4>
                <pre className="text-xs text-foreground whitespace-pre-wrap overflow-x-auto">
                  {error.stack}
                </pre>
              </div>

              {errorInfo && (
                <div className="bg-[var(--nous-bg-2)] border border-border rounded p-3">
                  <h4 className="text-sm font-medium text-foreground mb-2">
                    Component Stack
                  </h4>
                  <pre className="text-xs text-foreground whitespace-pre-wrap overflow-x-auto">
                    {errorInfo.componentStack}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Generic Error Boundary Class Component
export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  private retryTimeoutId?: NodeJS.Timeout;

  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      retryCount: 0,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return {
      hasError: true,
      error,
      errorId: `error-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ error, errorInfo });

    // Log error to console
    console.error(
      `Error in ${this.props.component || 'component'}:`,
      error,
      errorInfo
    );

    // Call custom error handler
    if (this.props.onError) {
      this.props.onError(error, errorInfo, this.state.errorId!);
    }

    // Log to external service (you can integrate with services like Sentry)
    this.logErrorToService(error, errorInfo);
  }

  componentWillUnmount() {
    if (this.retryTimeoutId) {
      clearTimeout(this.retryTimeoutId);
    }
  }

  private logErrorToService = (error: Error, errorInfo: ErrorInfo) => {
    try {
      // You can integrate with error logging services here
      // Example: Sentry.captureException(error, { extra: errorInfo });

      // For now, just log to console with structured data
      const errorData = {
        message: error.message,
        name: error.name,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
        component: this.props.component,
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
        url: window.location.href,
      };

      console.error('Error Boundary caught error:', errorData);
    } catch (loggingError) {
      console.error('Failed to log error:', loggingError);
    }
  };

  private handleRetry = () => {
    const { maxRetries = 3 } = this.props;
    const { retryCount } = this.state;

    if (retryCount >= maxRetries) {
      return;
    }

    // Clear error state and increment retry count
    this.setState((prevState) => ({
      hasError: false,
      error: undefined,
      errorInfo: undefined,
      retryCount: prevState.retryCount + 1,
    }));

    // Optional: Add a small delay before retry
    this.retryTimeoutId = setTimeout(() => {
      // Force a re-render by updating state
      this.setState({});
    }, 1000);
  };

  private handleDismiss = () => {
    this.setState({
      hasError: false,
      error: undefined,
      errorInfo: undefined,
    });
  };

  render() {
    if (this.state.hasError) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Use default fallback UI
      if (this.state.error) {
        return (
          <FallbackUI
            error={this.state.error}
            errorInfo={this.state.errorInfo}
            onRetry={this.handleRetry}
            onDismiss={this.handleDismiss}
            retryCount={this.state.retryCount}
            maxRetries={this.props.maxRetries}
            component={this.props.component}
            showErrorDetails={this.props.showErrorDetails}
            enableRetry={this.props.enableRetry}
          />
        );
      }

      // Minimal fallback if no error object
      return (
        <div className="p-4 bg-[var(--nous-mars)]/10 border border-[var(--nous-mars)]/40 rounded">
          <p className="text-[var(--nous-mars)]">
            An unexpected error occurred.
          </p>
        </div>
      );
    }

    return this.props.children;
  }
}

// Specialized error boundaries for specific components
export const RealtimeStatusErrorBoundary: React.FC<{
  children: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}> = ({ children, onError }) => (
  <ErrorBoundary
    component="Realtime Status Dashboard"
    onError={onError}
    maxRetries={3}
    showErrorDetails={process.env.NODE_ENV === 'development'}
    enableRetry={true}
  >
    {children}
  </ErrorBoundary>
);

export const DocumentProgressErrorBoundary: React.FC<{
  children: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}> = ({ children, onError }) => (
  <ErrorBoundary
    component="Document Progress Visualizer"
    onError={onError}
    maxRetries={5}
    showErrorDetails={process.env.NODE_ENV === 'development'}
    enableRetry={true}
  >
    {children}
  </ErrorBoundary>
);

export const NotificationCenterErrorBoundary: React.FC<{
  children: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}> = ({ children, onError }) => (
  <ErrorBoundary
    component="Notification Center"
    onError={onError}
    maxRetries={2}
    showErrorDetails={false} // Don't show error details for notifications
    enableRetry={false} // Don't allow retry for notification errors
  >
    {children}
  </ErrorBoundary>
);

export const ConnectionManagerErrorBoundary: React.FC<{
  children: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}> = ({ children, onError }) => (
  <ErrorBoundary
    component="Connection Manager"
    onError={onError}
    maxRetries={3}
    showErrorDetails={process.env.NODE_ENV === 'development'}
    enableRetry={true}
  >
    {children}
  </ErrorBoundary>
);

export const PerformanceMonitorErrorBoundary: React.FC<{
  children: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}> = ({ children, onError }) => (
  <ErrorBoundary
    component="Performance Monitor"
    onError={onError}
    maxRetries={2}
    showErrorDetails={process.env.NODE_ENV === 'development'}
    enableRetry={false}
  >
    {children}
  </ErrorBoundary>
);

// Hook for error handling
export const useErrorHandler = () => {
  const handleError = React.useCallback((error: Error, context?: string) => {
    console.error(`Error${context ? ` in ${context}` : ''}:`, error);

    // You can add external error logging here
    // Example: Sentry.captureException(error, { tags: { context } });
  }, []);

  const handleAsyncError = React.useCallback(
    async (asyncOperation: () => Promise<any>, context?: string) => {
      try {
        return await asyncOperation();
      } catch (error) {
        handleError(error as Error, context);
        throw error; // Re-throw for caller to handle
      }
    },
    [handleError]
  );

  return {
    handleError,
    handleAsyncError,
  };
};

// Error boundary provider for wrapping the entire app
export const AppErrorBoundary: React.FC<{
  children: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}> = ({ children, onError }) => (
  <ErrorBoundary
    component="Application"
    onError={onError}
    maxRetries={1}
    showErrorDetails={process.env.NODE_ENV === 'development'}
    enableRetry={false}
  >
    {children}
  </ErrorBoundary>
);

export default ErrorBoundary;
