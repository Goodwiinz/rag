import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { DraftGenerator } from '../DraftGenerator';

describe('DraftGenerator Accessibility', () => {
  const mockOnGenerate = jest.fn();

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

  it('supports keyboard navigation for Writing Style radio group', () => {
    render(<DraftGenerator onGenerate={mockOnGenerate} />);

    const academicRadio = screen.getByRole('radio', { name: /Academic/i });
    const technicalRadio = screen.getByRole('radio', { name: /Technical/i });
    const summaryRadio = screen.getByRole('radio', { name: /Summary/i });

    // Initial state: Academic selected
    expect(academicRadio).toHaveAttribute('aria-checked', 'true');
    expect(academicRadio).toHaveAttribute('tabindex', '0');
    expect(technicalRadio).toHaveAttribute('tabindex', '-1');
    expect(summaryRadio).toHaveAttribute('tabindex', '-1');

    // Focus academic radio
    academicRadio.focus();
    expect(document.activeElement).toBe(academicRadio);

    // Press ArrowRight -> Technical
    fireEvent.keyDown(academicRadio, { key: 'ArrowRight', code: 'ArrowRight' });
    expect(technicalRadio).toHaveAttribute('aria-checked', 'true');
    expect(technicalRadio).toHaveAttribute('tabindex', '0');
    expect(academicRadio).toHaveAttribute('tabindex', '-1');
    expect(document.activeElement).toBe(technicalRadio);

    // Press ArrowRight -> Summary
    fireEvent.keyDown(technicalRadio, { key: 'ArrowRight', code: 'ArrowRight' });
    expect(summaryRadio).toHaveAttribute('aria-checked', 'true');
    expect(document.activeElement).toBe(summaryRadio);

    // Press ArrowRight -> Loop back to Academic
    fireEvent.keyDown(summaryRadio, { key: 'ArrowRight', code: 'ArrowRight' });
    expect(academicRadio).toHaveAttribute('aria-checked', 'true');
    expect(document.activeElement).toBe(academicRadio);

    // Press ArrowLeft -> Summary (wrap around)
    fireEvent.keyDown(academicRadio, { key: 'ArrowLeft', code: 'ArrowLeft' });
    expect(summaryRadio).toHaveAttribute('aria-checked', 'true');
    expect(document.activeElement).toBe(summaryRadio);
  });
});
