/**
 * EntityErrorBoundary Component
 * Terminal Observatory themed error boundary for entity management pages.
 * Uses React class component (required for error boundaries).
 */

import React from 'react';
import { AlertCircle } from 'lucide-react';

interface EntityErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  onReset?: () => void;
}

interface EntityErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

export class EntityErrorBoundary extends React.Component<
  EntityErrorBoundaryProps,
  EntityErrorBoundaryState
> {
  constructor(props: EntityErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(
    error: Error
  ): Partial<EntityErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    console.error('[EntityErrorBoundary] Caught error:', error);
    console.error(
      '[EntityErrorBoundary] Component stack:',
      errorInfo.componentStack
    );
    this.setState({ errorInfo });
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div
          style={{
            minHeight: '100vh',
            backgroundColor: '#0a0f0a',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '2rem',
          }}
        >
          <div
            style={{
              maxWidth: '32rem',
              width: '100%',
              border: '1px solid rgba(255, 75, 75, 0.3)',
              borderRadius: '0.75rem',
              backgroundColor: 'rgba(255, 75, 75, 0.05)',
              padding: '2rem',
            }}
          >
            {/* Error icon and title */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '1rem',
                marginBottom: '1.5rem',
              }}
            >
              <div
                style={{
                  width: '3.5rem',
                  height: '3.5rem',
                  borderRadius: '50%',
                  backgroundColor: 'rgba(255, 75, 75, 0.1)',
                  border: '1px solid rgba(255, 75, 75, 0.3)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <AlertCircle className="w-7 h-7 text-red-500" />
              </div>
              <h2
                style={{
                  fontFamily: 'monospace',
                  fontSize: '0.875rem',
                  fontWeight: 700,
                  color: '#ff4b4b',
                  letterSpacing: '0.15em',
                  textTransform: 'uppercase',
                  textAlign: 'center',
                }}
              >
                ENTITY_COMPONENT_ERROR
              </h2>
            </div>

            {/* Error message */}
            <div
              style={{
                backgroundColor: 'rgba(255, 75, 75, 0.08)',
                border: '1px solid rgba(255, 75, 75, 0.15)',
                borderRadius: '0.5rem',
                padding: '0.75rem 1rem',
                marginBottom: '1rem',
              }}
            >
              <p
                style={{
                  fontFamily: 'monospace',
                  fontSize: '0.75rem',
                  color: '#ff4b4b',
                  wordBreak: 'break-word',
                }}
              >
                {this.state.error?.message ||
                  'An unexpected error occurred in the entity component.'}
              </p>
            </div>

            {/* Help text */}
            <p
              style={{
                fontFamily: 'monospace',
                fontSize: '0.6875rem',
                color: 'rgba(255, 255, 255, 0.4)',
                textAlign: 'center',
                marginBottom: '1.5rem',
                lineHeight: 1.6,
              }}
            >
              The entity component encountered a rendering error. You can retry,
              reload the page, or navigate back to the dashboard.
            </p>

            {/* Action buttons */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '0.5rem',
              }}
            >
              <button
                onClick={this.handleReset}
                style={{
                  width: '100%',
                  padding: '0.625rem 1rem',
                  fontFamily: 'monospace',
                  fontSize: '0.6875rem',
                  fontWeight: 700,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  color: '#0a0f0a',
                  backgroundColor: '#D4A039',
                  border: 'none',
                  borderRadius: '0.375rem',
                  cursor: 'pointer',
                }}
              >
                RETRY
              </button>
              <a
                href="/entities"
                style={{
                  display: 'block',
                  width: '100%',
                  padding: '0.625rem 1rem',
                  fontFamily: 'monospace',
                  fontSize: '0.6875rem',
                  fontWeight: 700,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  color: 'rgba(255, 255, 255, 0.7)',
                  backgroundColor: 'transparent',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  borderRadius: '0.375rem',
                  cursor: 'pointer',
                  textAlign: 'center',
                  textDecoration: 'none',
                  boxSizing: 'border-box',
                }}
              >
                RELOAD PAGE
              </a>
              <a
                href="/dashboard"
                style={{
                  display: 'block',
                  width: '100%',
                  padding: '0.625rem 1rem',
                  fontFamily: 'monospace',
                  fontSize: '0.6875rem',
                  fontWeight: 700,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  color: 'rgba(255, 255, 255, 0.4)',
                  backgroundColor: 'transparent',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '0.375rem',
                  cursor: 'pointer',
                  textAlign: 'center',
                  textDecoration: 'none',
                  boxSizing: 'border-box',
                }}
              >
                DASHBOARD
              </a>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
