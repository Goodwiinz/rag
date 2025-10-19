import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { errorTracker } from '@/utils/errorTracking';
import {
  AlertTriangle,
  RefreshCw,
  Bug,
  Send,
  ChevronDown,
  ChevronUp,
  Copy
} from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  showDetails?: boolean;
  component?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  errorId: string | null;
  showDetails: boolean;
  reportSent: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  private retryCount = 0;
  private maxRetries = 3;

  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: null,
      showDetails: false,
      reportSent: false
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return {
      hasError: true,
      error,
      errorId: `ERR-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({
      error,
      errorInfo,
      errorId: this.state.errorId || `ERR-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`
    });

    // Track the error
    errorTracker.captureComponentError(
      this.props.component || 'UnknownComponent',
      error,
      errorInfo
    );

    // Call custom error handler if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    // Log additional context
    errorTracker.error('Error boundary caught an error', error, {
      component: this.props.component || 'UnknownComponent',
      action: 'ErrorBoundary',
      additionalData: {
        errorId: this.state.errorId,
        errorInfo: errorInfo.componentStack,
        retryCount: this.retryCount
      }
    });
  }

  handleRetry = () => {
    if (this.retryCount < this.maxRetries) {
      this.retryCount++;
      errorTracker.info('User initiated retry after error', {
        component: this.props.component || 'UnknownComponent',
        action: 'ErrorRetry',
        additionalData: {
          errorId: this.state.errorId,
          retryCount: this.retryCount
        }
      });

      this.setState({
        hasError: false,
        error: null,
        errorInfo: null,
        errorId: null,
        showDetails: false,
        reportSent: false
      }, () => {
        // Reset retry count after successful state reset
        this.retryCount = 0;
      });
    }
  };

  handleReportError = async () => {
    if (!this.state.error || !this.state.errorId) return;

    try {
      // In a real implementation, this would send to your error reporting service
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));

      this.setState({ reportSent: true });
      errorTracker.info('Error report sent successfully', {
        component: this.props.component || 'UnknownComponent',
        action: 'ErrorReportSent',
        additionalData: { errorId: this.state.errorId }
      });
    } catch (reportError) {
      errorTracker.error('Failed to send error report', reportError as Error, {
        component: this.props.component || 'UnknownComponent',
        action: 'ErrorReportFailed',
        additionalData: { errorId: this.state.errorId }
      });
    }
  };

  toggleDetails = () => {
    this.setState(prevState => ({ showDetails: !prevState.showDetails }));
  };

  copyErrorDetails = () => {
    if (!this.state.error) return;

    const errorDetails = `
Error ID: ${this.state.errorId}
Component: ${this.props.component || 'Unknown'}
Message: ${this.state.error.message}
Stack Trace: ${this.state.error.stack}
Component Stack: ${this.state.errorInfo?.componentStack}
Timestamp: ${new Date().toISOString()}
    `.trim();

    navigator.clipboard.writeText(errorDetails).then(() => {
      errorTracker.info('Error details copied to clipboard', {
        component: this.props.component || 'UnknownComponent',
        action: 'ErrorDetailsCopied',
        additionalData: { errorId: this.state.errorId }
      });
    });
  };

  render() {
    if (this.state.hasError) {
      // Custom fallback UI if provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default error UI
      return (
        <div className="min-h-[400px] flex items-center justify-center p-4">
          <Card className="w-full max-w-2xl">
            <CardHeader>
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-red-500" />
                <CardTitle className="text-red-700">Something went wrong</CardTitle>
              </div>
              <CardDescription>
                {this.props.component ? `An error occurred in ${this.props.component}` : 'An unexpected error occurred'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Error Message */}
              <Alert>
                <Bug className="h-4 w-4" />
                <AlertTitle>Error Details</AlertTitle>
                <AlertDescription className="mt-2">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">ID: {this.state.errorId}</Badge>
                      {this.props.component && (
                        <Badge variant="secondary">{this.props.component}</Badge>
                      )}
                    </div>
                    <p className="text-sm">{this.state.error?.message}</p>
                  </div>
                </AlertDescription>
              </Alert>

              {/* Actions */}
              <div className="flex flex-wrap gap-2">
                {this.retryCount < this.maxRetries && (
                  <Button onClick={this.handleRetry} variant="default" size="sm">
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Try Again ({this.maxRetries - this.retryCount} attempts left)
                  </Button>
                )}

                {!this.state.reportSent ? (
                  <Button onClick={this.handleReportError} variant="outline" size="sm">
                    <Send className="h-4 w-4 mr-2" />
                    Report Error
                  </Button>
                ) : (
                  <Badge variant="secondary" className="text-green-700">
                    ✓ Report Sent
                  </Badge>
                )}

                <Button onClick={this.toggleDetails} variant="ghost" size="sm">
                  {this.state.showDetails ? (
                    <ChevronUp className="h-4 w-4 mr-2" />
                  ) : (
                    <ChevronDown className="h-4 w-4 mr-2" />
                  )}
                  {this.state.showDetails ? 'Hide' : 'Show'} Details
                </Button>

                <Button onClick={this.copyErrorDetails} variant="ghost" size="sm">
                  <Copy className="h-4 w-4 mr-2" />
                  Copy
                </Button>
              </div>

              {/* Detailed Error Information */}
              {this.state.showDetails && (
                <div className="space-y-4 border-t pt-4">
                  <div>
                    <h4 className="font-medium mb-2">Stack Trace</h4>
                    <pre className="text-xs bg-gray-50 p-3 rounded overflow-auto max-h-40 whitespace-pre-wrap">
                      {this.state.error?.stack || 'No stack trace available'}
                    </pre>
                  </div>

                  {this.state.errorInfo?.componentStack && (
                    <div>
                      <h4 className="font-medium mb-2">Component Stack</h4>
                      <pre className="text-xs bg-gray-50 p-3 rounded overflow-auto max-h-40 whitespace-pre-wrap">
                        {this.state.errorInfo.componentStack}
                      </pre>
                    </div>
                  )}

                  <div>
                    <h4 className="font-medium mb-2">Debug Information</h4>
                    <div className="text-sm space-y-1">
                      <div><strong>Retry Count:</strong> {this.retryCount}/{this.maxRetries}</div>
                      <div><strong>User Agent:</strong> {navigator.userAgent}</div>
                      <div><strong>URL:</strong> {window.location.href}</div>
                      <div><strong>Timestamp:</strong> {new Date().toLocaleString()}</div>
                    </div>
                  </div>
                </div>
              )}

              {/* Retry limit reached message */}
              {this.retryCount >= this.maxRetries && (
                <Alert>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>Retry limit reached</AlertTitle>
                  <AlertDescription>
                    Maximum retry attempts ({this.maxRetries}) have been reached. Please refresh the page or contact support if the problem persists.
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>
        </div>
      );
    }

    return this.props.children;
  }
}

// Hook for functional components
export const useErrorHandler = () => {
  const handleError = (error: Error, context?: string) => {
    errorTracker.captureError(error, {
      component: context || 'HookComponent',
      action: 'ErrorHandler'
    });
  };

  const reportError = (message: string, error?: Error, context?: string) => {
    errorTracker.error(message, error, {
      component: context || 'HookComponent',
      action: 'ReportError'
    });
  };

  return {
    handleError,
    reportError,
    captureError: errorTracker.captureError,
    captureException: errorTracker.captureException
  };
};

// HOC for wrapping components with error boundary
export const withErrorBoundary = <P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<Props, 'children'>
) => {
  const WrappedComponent = (props: P) => (
    <ErrorBoundary {...errorBoundaryProps}>
      <Component {...props} />
    </ErrorBoundary>
  );

  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name})`;

  return WrappedComponent;
};