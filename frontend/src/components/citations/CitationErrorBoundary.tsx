'use client';

/**
 * Citation Error Boundary
 * Catches and displays errors in citation components
 */

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class CitationErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[CitationErrorBoundary] Error caught:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="p-6 bg-[#0a0a0a] border border-red-500/30 rounded-lg text-center">
          <AlertCircle className="h-10 w-10 text-red-400 mx-auto mb-3" />
          <h3 className="font-mono font-medium text-red-400 mb-2">
            Citation Component Error
          </h3>
          <p className="text-sm text-muted-foreground font-mono mb-4">
            {this.state.error?.message || 'An unexpected error occurred'}
          </p>
          <button
            onClick={this.handleReset}
            className="inline-flex items-center gap-2 px-4 py-2 bg-red-500/10 text-red-400 border border-red-500/30 rounded font-mono text-sm hover:bg-red-500/20 transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default CitationErrorBoundary;
