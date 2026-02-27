import React from 'react';
import { render, screen } from '@testing-library/react';
import { Button } from '../button';

// Mock Spinner to avoid dealing with svg internals in tests if needed,
// but checking for role="status" is better integration test.
// The real Spinner has role="status" and aria-label="Loading"

describe('Button', () => {
  it('renders correctly', () => {
    render(<Button>Click me</Button>);
    expect(
      screen.getByRole('button', { name: /click me/i })
    ).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeEnabled();
  });

  it('shows spinner and disables button when isLoading is true', () => {
    render(<Button isLoading>Click me</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Loading');
    expect(screen.getByText('Click me')).toBeInTheDocument();
  });

  it('shows loading text when provided', () => {
    render(
      <Button isLoading loadingText="Saving...">
        Save
      </Button>
    );
    expect(screen.getByRole('button')).toBeDisabled();
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText('Saving...')).toBeInTheDocument();
    expect(screen.queryByText('Save')).not.toBeInTheDocument();
  });

  it('hides children when loading in icon mode', () => {
    render(
      <Button size="icon" isLoading>
        <span>Icon</span>
      </Button>
    );
    expect(screen.getByRole('button')).toBeDisabled();
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.queryByText('Icon')).not.toBeInTheDocument();
  });

  it('renders correctly with asChild', () => {
    render(
      <Button asChild>
        <a href="/test">Link</a>
      </Button>
    );
    const link = screen.getByRole('link', { name: /link/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/test');
  });

  it('ignores loading state when asChild is true', () => {
    render(
      <Button asChild isLoading>
        <a href="/test">Link</a>
      </Button>
    );
    const link = screen.getByRole('link', { name: /link/i });
    expect(link).toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});
