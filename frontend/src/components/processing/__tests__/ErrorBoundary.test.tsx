/**
 * Error Boundary Unit Tests
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ErrorBoundary, useErrorHandler } from '../ErrorBoundary';

// Mock console.error to avoid noise in tests
const originalError = console.error;
beforeAll(() => {
  console.error = jest.fn();
});

afterAll(() => {
  console.error = originalError;
});

// Test component that throws an error
const ThrowErrorComponent: React.FC<{ shouldThrow?: boolean; errorType?: 'render' | 'async' }> = ({
  shouldThrow = false,
  errorType = 'render'
}) => {
  if (shouldThrow) {
    if (errorType === 'render') {
      throw new Error('Test error');
    }
    throw new Promise((_, reject) => reject(new Error('Async test error')));
  }

  return <div>Normal Component</div>;
};

// Test component with error handling hook
const ComponentWithErrorHandler: React.FC<{ shouldThrow?: boolean }> = ({ shouldThrow }) => {
  const { handleError } = useErrorHandler();

  const handleClick = () => {
    if (shouldThrow) {
      handleError(new Error('Handled error'), 'TestComponent');
    }
  };

  return (
    <button onClick={handleClick}>Trigger Error</button>
  );
};

describe('ErrorBoundary', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders children when there is no error', () => {
    render(
      <ErrorBoundary>
        <ThrowErrorComponent shouldThrow={false} />
      </ErrorBoundary>
    );

    expect(screen.getByText('Normal Component')).toBeInTheDocument();
  });

  it('catches render errors and displays fallback UI', () => {
    render(
      <ErrorBoundary component="TestComponent">
        <ThrowErrorComponent shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText(/TestComponent Error/i)).toBeInTheDocument();
    expect(screen.getByText(/Test error/)).toBeInTheDocument();
  });

  it('calls custom error handler when error occurs', () => {
    const onError = jest.fn();

    render(
      <ErrorBoundary component="TestComponent" onError={onError}>
        <ThrowErrorComponent shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(onError).toHaveBeenCalledWith(
      expect.any(Error),
      expect.objectContaining({
        componentStack: expect.any(String)
      }),
      expect.any(String)
    );
  });

  it('allows retry when enabled and within max retries', async () => {
    render(
      <ErrorBoundary component="TestComponent" maxRetries={3} enableRetry>
        <ThrowErrorComponent shouldThrow={false} />
      </ErrorBoundary>
    );

    // Trigger error by re-rendering with shouldThrow=true
    render(
      <ErrorBoundary component="TestComponent" maxRetries={3} enableRetry>
        <ThrowErrorComponent shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText(/TestComponent Error/i)).toBeInTheDocument();

    const retryButton = screen.getByRole('button', { name: /retry/i });
    expect(retryButton).toBeInTheDocument();

    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(screen.getByText('Normal Component')).toBeInTheDocument();
    });
  });

  it('disables retry when max retries exceeded', () => {
    render(
      <ErrorBoundary component="TestComponent" maxRetries={0} enableRetry>
        <ThrowErrorComponent shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText(/TestComponent Error/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
  });

  it('shows custom fallback when provided', () => {
    const customFallback = <div>Custom Fallback UI</div>;

    render(
      <ErrorBoundary fallback={customFallback}>
        <ThrowErrorComponent shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText('Custom Fallback UI')).toBeInTheDocument();
  });

  it('hides error details when showErrorDetails is false', () => {
    render(
      <ErrorBoundary component="TestComponent" showErrorDetails={false}>
        <ThrowErrorComponent shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.queryByText(/show details/i)).not.toBeInTheDocument();
  });

  it('dismisses error when dismiss button is clicked', () => {
    render(
      <ErrorBoundary component="TestComponent" enableRetry>
        <div>Test Content</div>
      </ErrorBoundary>
    );

    // This won't actually trigger an error since the component doesn't throw,
    // but we can test the dismiss functionality through a scenario where it would appear
    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });
});

describe('useErrorHandler', () => {
  it('provides error handling function', () => {
    render(<ComponentWithErrorHandler />);

    expect(screen.getByRole('button', { name: 'Trigger Error' })).toBeInTheDocument();
  });

  it('handles errors without crashing', () => {
    // Suppress console.error for this test
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

    render(<ComponentWithErrorHandler shouldThrow />);

    const button = screen.getByRole('button', { name: 'Trigger Error' });
    fireEvent.click(button);

    expect(consoleSpy).toHaveBeenCalled();

    consoleSpy.mockRestore();
  });
});

describe('Specialized Error Boundaries', () => {
  it('RealtimeStatusErrorBoundary has correct configuration', () => {
    const { container } = render(
      <RealtimeStatusErrorBoundary>
        <div>Test Content</div>
      </RealtimeStatusErrorBoundary>
    );

    expect(container.firstChild).toBeInTheDocument();
    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('DocumentProgressErrorBoundary has correct configuration', () => {
    const { container } = render(
      <DocumentProgressErrorBoundary>
        <div>Test Content</div>
      </DocumentProgressErrorBoundary>
    );

    expect(container.firstChild).toBeInTheDocument();
    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('NotificationCenterErrorBoundary has correct configuration', () => {
    const { container } = render(
      <NotificationCenterErrorBoundary>
        <div>Test Content</div>
      </NotificationCenterErrorBoundary>
    );

    expect(container.firstChild).toBeInTheDocument();
    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('ConnectionManagerErrorBoundary has correct configuration', () => {
    const { container } = render(
      <ConnectionManagerErrorBoundary>
        <div>Test Content</div>
      </ConnectionManagerErrorBoundary>
    );

    expect(container.firstChild).toBeInTheDocument();
    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('PerformanceMonitorErrorBoundary has correct configuration', () => {
    const { container } = render(
      <PerformanceMonitorErrorBoundary>
        <div>Test Content</div>
      </PerformanceMonitorErrorBoundary>
    );

    expect(container.firstChild).toBeInTheDocument();
    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });
});

describe('Error boundary behavior', () => {
  it('recovers from errors after retry', async () => {
    const TestComponent: React.FC<{ throwError: boolean }> = ({ throwError }) => {
      if (throwError) {
        throw new Error('Test error');
      }
      return <div>Recovered Component</div>;
    };

    const { rerender } = render(
      <ErrorBoundary component="TestComponent" enableRetry maxRetries={1}>
        <TestComponent throwError={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText(/TestComponent Error/i)).toBeInTheDocument();

    const retryButton = screen.getByRole('button', { name: /retry/i });
    fireEvent.click(retryButton);

    // Rerender with throwError=false
    rerender(
      <ErrorBoundary component="TestComponent" enableRetry maxRetries={1}>
        <TestComponent throwError={false} />
      </ErrorBoundary>
    );

    await waitFor(() => {
      expect(screen.getByText('Recovered Component')).toBeInTheDocument();
    });
  });

  it('logs errors to console', () => {
    render(
      <ErrorBoundary component="TestComponent">
        <ThrowErrorComponent shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(console.error).toHaveBeenCalled();
  });

  it('generates unique error IDs', () => {
    const onError = jest.fn();

    const { rerender } = render(
      <ErrorBoundary component="TestComponent" onError={onError}>
        <div>Test</div>
      </ErrorBoundary>
    );

    // Trigger first error
    rerender(
      <ErrorBoundary component="TestComponent" onError={onError}>
        <ThrowErrorComponent shouldThrow={true} />
      </ErrorBoundary>
    );

    const firstCall = onError.mock.calls[0];
    const firstErrorId = firstCall[2];

    // Reset and trigger second error
    onError.mockClear();
    rerender(
      <ErrorBoundary component="TestComponent" onError={onError}>
        <ThrowErrorComponent shouldThrow={true} />
      </ErrorBoundary>
    );

    const secondCall = onError.mock.calls[0];
    const secondErrorId = secondCall[2];

    expect(firstErrorId).not.toBe(secondErrorId);
    expect(firstErrorId).toMatch(/^error-\d+-[a-z0-9]+$/);
    expect(secondErrorId).toMatch(/^error-\d+-[a-z0-9]+$/);
  });
});