'use client';

/**
 * Research Error Boundary
 * Catches and displays errors in research components
 */

import { AlertCircle, Home, RefreshCw } from 'lucide-react';
import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ResearchErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[ResearchErrorBoundary] Error caught:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="p-8 bg-card border border-destructive/30 rounded-lg text-center">
          <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
          <h3 className="font-semibold text-destructive text-lg mb-2">
            Something went wrong
          </h3>
          <p className="text-sm text-muted-foreground mb-6 max-w-md mx-auto">
            {this.state.error?.message ||
              'An unexpected error occurred in the research component'}
          </p>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={this.handleReset}
              className="inline-flex items-center gap-2 px-4 py-2 bg-destructive/10 text-destructive border border-destructive/30 rounded text-sm hover:bg-destructive/20 transition-colors"
            >
              <RefreshCw className="h-4 w-4" />
              Try Again
            </button>
            {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- Class component error boundary intentionally uses native anchor for reliable navigation during error states */}
            <a
              href="/projects"
              className="inline-flex items-center gap-2 px-4 py-2 bg-muted text-muted-foreground border border-border rounded text-sm hover:border-foreground/30 transition-colors"
            >
              <Home className="h-4 w-4" />
              Back to Projects
            </a>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ResearchErrorBoundary;
