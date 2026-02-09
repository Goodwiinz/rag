'use client';

/**
 * Research Error Boundary
 * Catches and displays errors in research components
 */

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertCircle, RefreshCw, Home } from 'lucide-react';

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
        <div className="p-8 bg-[#0a0a0a] border border-red-500/30 rounded-lg text-center">
          <AlertCircle className="h-12 w-12 text-red-400 mx-auto mb-4" />
          <h3 className="font-mono font-bold text-red-400 text-lg mb-2">
            Something went wrong
          </h3>
          <p className="text-sm text-gray-500 font-mono mb-6 max-w-md mx-auto">
            {this.state.error?.message || 'An unexpected error occurred in the research component'}
          </p>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={this.handleReset}
              className="inline-flex items-center gap-2 px-4 py-2 bg-red-500/10 text-red-400 border border-red-500/30 rounded font-mono text-sm hover:bg-red-500/20 transition-colors"
            >
              <RefreshCw className="h-4 w-4" />
              Try Again
            </button>
            <a
              href="/projects"
              className="inline-flex items-center gap-2 px-4 py-2 bg-[#1a1a1a] text-gray-400 border border-[#333] rounded font-mono text-sm hover:border-[#555] transition-colors"
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
