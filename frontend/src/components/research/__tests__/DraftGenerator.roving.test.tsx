import { beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { DraftGenerator } from '../DraftGenerator';

describe('DraftGenerator Keyboard Navigation', () => {
  const mockOnGenerate = vi.fn();

  beforeEach(() => {
    mockOnGenerate.mockClear();
  });

  it('navigates style options with arrow keys (roving tabindex)', () => {
    render(<DraftGenerator onGenerate={mockOnGenerate} />);

    // Get all style radio buttons
    const academicRadio = screen.getByRole('radio', { name: /Academic/i });
    const technicalRadio = screen.getByRole('radio', { name: /Technical/i });
    const summaryRadio = screen.getByRole('radio', { name: /Summary/i });

    // Initial state: Academic is selected and focusable (tabIndex=0)
    // Others should not be focusable via tab (tabIndex=-1)
    expect(academicRadio).toHaveAttribute('aria-checked', 'true');
    expect(academicRadio).toHaveAttribute('tabIndex', '0');
    expect(technicalRadio).toHaveAttribute('tabIndex', '-1');
    expect(summaryRadio).toHaveAttribute('tabIndex', '-1');

    // Focus the first radio button
    academicRadio.focus();
    expect(document.activeElement).toBe(academicRadio);

    // Press ArrowRight to move to Technical
    fireEvent.keyDown(academicRadio, { key: 'ArrowRight', code: 'ArrowRight' });

    // Expect Technical to be checked and focused
    expect(technicalRadio).toHaveAttribute('aria-checked', 'true');
    expect(document.activeElement).toBe(technicalRadio);

    // Tab indices should update
    expect(academicRadio).toHaveAttribute('tabIndex', '-1');
    expect(technicalRadio).toHaveAttribute('tabIndex', '0');

    // Press ArrowRight to move to Summary
    fireEvent.keyDown(technicalRadio, { key: 'ArrowRight', code: 'ArrowRight' });
    expect(summaryRadio).toHaveAttribute('aria-checked', 'true');
    expect(document.activeElement).toBe(summaryRadio);

    // Press ArrowRight again to loop back to Academic
    fireEvent.keyDown(summaryRadio, { key: 'ArrowRight', code: 'ArrowRight' });
    expect(academicRadio).toHaveAttribute('aria-checked', 'true');
    expect(document.activeElement).toBe(academicRadio);

    // Press ArrowLeft to go back to Summary
    fireEvent.keyDown(academicRadio, { key: 'ArrowLeft', code: 'ArrowLeft' });
    expect(summaryRadio).toHaveAttribute('aria-checked', 'true');
    expect(document.activeElement).toBe(summaryRadio);
  });
});
