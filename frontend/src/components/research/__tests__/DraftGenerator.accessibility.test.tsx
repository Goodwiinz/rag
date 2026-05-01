import { beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { DraftGenerator } from '../DraftGenerator';

describe('DraftGenerator Accessibility', () => {
  const mockOnGenerate = vi.fn();

  beforeEach(() => {
    mockOnGenerate.mockClear();
  });

  it('has accessible label for themes input', () => {
    render(<DraftGenerator onGenerate={mockOnGenerate} />);

    // Check if label is associated with input
    const input = screen.getByLabelText(/Themes \/ Topics/i);
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute('type', 'text');
  });

  it('has accessible label for Add Theme button', () => {
    render(<DraftGenerator onGenerate={mockOnGenerate} />);

    const addButton = screen.getByLabelText('Add theme');
    expect(addButton).toBeInTheDocument();
  });

  it('has accessible label for Remove Theme button when themes exist', () => {
    render(<DraftGenerator onGenerate={mockOnGenerate} />);

    // Add a theme first
    const input = screen.getByLabelText(/Themes \/ Topics/i);
    fireEvent.change(input, { target: { value: 'test-theme' } });

    const addButton = screen.getByLabelText('Add theme');
    fireEvent.click(addButton);

    // Check for remove button
    const removeButton = screen.getByLabelText('Remove theme test-theme');
    expect(removeButton).toBeInTheDocument();
  });

  it('has accessible radio group for Writing Style', () => {
    render(<DraftGenerator onGenerate={mockOnGenerate} />);

    const radioGroup = screen.getByRole('radiogroup', { name: /Writing Style/i });
    expect(radioGroup).toBeInTheDocument();

    const radios = screen.getAllByRole('radio');
    expect(radios).toHaveLength(3);

    // Check default selection
    const academicRadio = screen.getByRole('radio', { name: /Academic/i });
    expect(academicRadio).toHaveAttribute('aria-checked', 'true');
  });

  it('has accessible label for Max Sections slider', () => {
    render(<DraftGenerator onGenerate={mockOnGenerate} />);

    const slider = screen.getByLabelText(/Max Sections/i);
    expect(slider).toBeInTheDocument();
    expect(slider).toHaveAttribute('type', 'range');
  });

  it('has accessible toggle switch for Include Abstract', () => {
    render(<DraftGenerator onGenerate={mockOnGenerate} />);

    const toggle = screen.getByRole('switch', { name: /Include Abstract/i });
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute('aria-checked', 'true');

    // Test toggling
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-checked', 'false');
  });
});
