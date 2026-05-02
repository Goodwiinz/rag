import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { DraftGenerator } from '@/components/research/DraftGenerator';

describe('DraftGenerator', () => {
  it('renders initial state with disabled generate button', () => {
    render(<DraftGenerator onGenerate={vi.fn()} documentCount={3} />);

    expect(
      screen.getByRole('heading', { name: 'Generate Literature Review' })
    ).toBeInTheDocument();
    expect(
      screen.getByText('The review will analyze 3 documents from this project.')
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /generate literature review/i })
    ).toBeDisabled();
  });

  it('adds theme via Enter and enables generate', () => {
    const onGenerate = vi.fn();
    render(<DraftGenerator onGenerate={onGenerate} />);

    const themeInput = screen.getByPlaceholderText(
      'Enter a theme and press Enter...'
    );
    fireEvent.change(themeInput, { target: { value: 'methodology' } });
    fireEvent.keyDown(themeInput, { key: 'Enter' });

    expect(screen.getByText('methodology')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /generate literature review/i })
    ).not.toBeDisabled();
  });

  it('submits selected style, sections and abstract options', () => {
    const onGenerate = vi.fn();
    render(<DraftGenerator onGenerate={onGenerate} />);

    const themeInput = screen.getByPlaceholderText(
      'Enter a theme and press Enter...'
    );
    fireEvent.change(themeInput, { target: { value: 'findings' } });
    fireEvent.keyDown(themeInput, { key: 'Enter' });

    fireEvent.click(screen.getByRole('radio', { name: /technical/i }));

    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '7' } });

    fireEvent.click(screen.getByRole('switch', { name: /include abstract/i }));

    fireEvent.click(
      screen.getByRole('button', { name: /generate literature review/i })
    );

    expect(onGenerate).toHaveBeenCalledWith({
      themes: ['findings'],
      style: 'technical',
      maxSections: 7,
      includeAbstract: false,
    });
  });

  it('shows loading state label', () => {
    render(<DraftGenerator onGenerate={vi.fn()} loading />);
    expect(screen.getByText('Generating...')).toBeInTheDocument();
  });
});
