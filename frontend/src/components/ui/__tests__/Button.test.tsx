import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Button } from '../button';

describe('Button Component', () => {
  it('renders children correctly', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument();
  });

  it('renders spinner when isLoading is true', () => {
    render(<Button isLoading>Click me</Button>);
    // Spinner has role "status" and aria-label "Loading"
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeDisabled();
    expect(screen.getByRole('button')).toHaveAttribute('aria-busy', 'true');
  });

  it('renders loading text when provided', () => {
    render(<Button isLoading loadingText="Processing...">Click me</Button>);
    expect(screen.getByRole('button')).toHaveTextContent('Processing...');
    // Should verify it does NOT have "Click me" - use queryByText or just check textContent
    expect(screen.queryByText('Click me')).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders children when loadingText is not provided but isLoading is true', () => {
    render(<Button isLoading>Click me</Button>);
    expect(screen.getByRole('button')).toHaveTextContent('Click me');
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('is disabled when disabled prop is true', () => {
    render(<Button disabled>Click me</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('is disabled when isLoading is true regardless of disabled prop', () => {
    render(<Button isLoading disabled={false}>Click me</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });
});
