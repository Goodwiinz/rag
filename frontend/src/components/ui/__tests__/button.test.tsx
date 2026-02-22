import { render, screen } from '@testing-library/react';
import { Button } from '../button';

describe('Button', () => {
  it('renders correctly', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument();
  });

  it('shows loading state', () => {
    render(<Button isLoading>Click me</Button>);
    const button = screen.getByRole('button');
    // It should be disabled
    expect(button).toBeDisabled();
    // It should show a spinner (which has role="status")
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('shows custom loading text', () => {
    render(<Button isLoading loadingText="Saving...">Click me</Button>);
    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
    expect(screen.getByText('Saving...')).toBeInTheDocument();
    // "Click me" should NOT be visible if loadingText replaces it
    expect(screen.queryByText('Click me')).not.toBeInTheDocument();
  });

  it('respects asChild prop', () => {
    // When asChild is true, it renders the child. loading props are valid on Button but ignored visually
    render(<Button asChild isLoading><a href="#">Link</a></Button>);
    const link = screen.getByRole('link', { name: /link/i });
    expect(link).toBeInTheDocument();
    // Spinner should NOT be present because asChild ignores isLoading visual changes
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});
