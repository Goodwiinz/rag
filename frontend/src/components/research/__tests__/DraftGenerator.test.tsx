/**
 * Unit tests for DraftGenerator component
 *
 * Tests theme input (Enter key, Plus button, removal), style selection,
 * max sections slider, abstract toggle, generate button states, and
 * document count display using @testing-library/react.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  DraftGenerator,
  type GenerationConfig,
} from '@/components/research/DraftGenerator';

describe('DraftGenerator', () => {
  const defaultOnGenerate = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the component with generate button', () => {
    render(<DraftGenerator onGenerate={defaultOnGenerate} />);

    // The h3 heading and button both say "Generate Literature Review"
    expect(
      screen.getAllByText('Generate Literature Review').length
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Themes / Topics *')).toBeInTheDocument();
    expect(screen.getByText('Writing Style')).toBeInTheDocument();
    expect(screen.getByText('Include Abstract')).toBeInTheDocument();
  });

  it('adds a theme via input and Enter key', () => {
    render(<DraftGenerator onGenerate={defaultOnGenerate} />);

    const input = screen.getByPlaceholderText(
      'Enter a theme and press Enter...'
    );

    fireEvent.change(input, { target: { value: 'machine learning' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    expect(screen.getByText('machine learning')).toBeInTheDocument();
    // Input should be cleared after adding
    expect(input).toHaveValue('');
  });

  it('adds a theme via the Plus button click', () => {
    render(<DraftGenerator onGenerate={defaultOnGenerate} />);

    const input = screen.getByPlaceholderText(
      'Enter a theme and press Enter...'
    );

    fireEvent.change(input, { target: { value: 'deep learning' } });

    // The Plus button is the only non-style, non-generate, non-toggle button
    // with the Plus icon. It is next to the input in the flex row.
    const buttons = screen.getAllByRole('button');
    // The Plus button is the one that is NOT the style buttons, not the
    // abstract toggle, and not the generate button. It should be the first
    // button rendered (right after the input).
    const plusButton = buttons[0];
    fireEvent.click(plusButton);

    expect(screen.getByText('deep learning')).toBeInTheDocument();
    expect(input).toHaveValue('');
  });

  it('removes a theme via the X button on the chip', () => {
    render(<DraftGenerator onGenerate={defaultOnGenerate} />);

    const input = screen.getByPlaceholderText(
      'Enter a theme and press Enter...'
    );

    // Add two themes
    fireEvent.change(input, { target: { value: 'NLP' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    fireEvent.change(input, { target: { value: 'Computer Vision' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    expect(screen.getByText('NLP')).toBeInTheDocument();
    expect(screen.getByText('Computer Vision')).toBeInTheDocument();

    // Each theme chip has a remove button (the X icon).
    // The chip for 'NLP' contains the text 'NLP' and a child button.
    const nlpChip = screen.getByText('NLP').closest('span');
    const removeButton = nlpChip?.querySelector('button');
    expect(removeButton).toBeTruthy();
    fireEvent.click(removeButton!);

    expect(screen.queryByText('NLP')).not.toBeInTheDocument();
    expect(screen.getByText('Computer Vision')).toBeInTheDocument();
  });

  it('disables the generate button when no themes are added', () => {
    render(<DraftGenerator onGenerate={defaultOnGenerate} />);

    const generateButton = screen.getByRole('button', {
      name: /generate literature review/i,
    });

    expect(generateButton).toBeDisabled();
  });

  it('calls onGenerate with the correct config when generate is clicked', () => {
    const onGenerate = jest.fn();
    render(<DraftGenerator onGenerate={onGenerate} />);

    const input = screen.getByPlaceholderText(
      'Enter a theme and press Enter...'
    );

    // Add a theme
    fireEvent.change(input, { target: { value: 'healthcare AI' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    // Select 'technical' style
    const technicalButton = screen.getByRole('button', {
      name: /technical/i,
    });
    fireEvent.click(technicalButton);

    // Adjust max sections slider to 7
    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '7' } });

    // Toggle abstract off (it defaults to on, so click toggles it off)
    const abstractToggle = screen
      .getByText('Include Abstract')
      .closest('div')
      ?.querySelector('button');
    expect(abstractToggle).toBeTruthy();
    fireEvent.click(abstractToggle!);

    // Click generate
    const generateButton = screen.getByRole('button', {
      name: /generate literature review/i,
    });
    expect(generateButton).toBeEnabled();
    fireEvent.click(generateButton);

    expect(onGenerate).toHaveBeenCalledTimes(1);
    const calledConfig: GenerationConfig = onGenerate.mock.calls[0][0];
    expect(calledConfig.themes).toEqual(['healthcare AI']);
    expect(calledConfig.style).toBe('technical');
    expect(calledConfig.maxSections).toBe(7);
    expect(calledConfig.includeAbstract).toBe(false);
  });

  it('shows loading state when loading prop is true', () => {
    render(<DraftGenerator onGenerate={defaultOnGenerate} loading={true} />);

    expect(screen.getByText('Generating...')).toBeInTheDocument();
    // The button text changes to "Generating..." but the h3 heading remains
    const generatingButton = screen
      .getByText('Generating...')
      .closest('button');
    expect(generatingButton).toBeInTheDocument();
    expect(generatingButton).toBeDisabled();
  });

  it('disables the generate button when loading even with themes', () => {
    render(<DraftGenerator onGenerate={defaultOnGenerate} loading={true} />);

    // Add a theme first so the only disable reason would be loading
    const input = screen.getByPlaceholderText(
      'Enter a theme and press Enter...'
    );
    fireEvent.change(input, { target: { value: 'test theme' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    // The button with "Generating..." text should be disabled
    const generatingButton = screen
      .getByText('Generating...')
      .closest('button');
    expect(generatingButton).toBeDisabled();
  });

  it('displays document count info when documentCount is provided', () => {
    render(
      <DraftGenerator onGenerate={defaultOnGenerate} documentCount={12} />
    );

    expect(
      screen.getByText(
        'The review will analyze 12 documents from this project.'
      )
    ).toBeInTheDocument();
  });

  it('displays singular "document" when documentCount is 1', () => {
    render(<DraftGenerator onGenerate={defaultOnGenerate} documentCount={1} />);

    expect(
      screen.getByText('The review will analyze 1 document from this project.')
    ).toBeInTheDocument();
  });

  it('does not display document count info when documentCount is 0', () => {
    render(<DraftGenerator onGenerate={defaultOnGenerate} documentCount={0} />);

    expect(
      screen.queryByText(/The review will analyze/)
    ).not.toBeInTheDocument();
  });

  it('does not add duplicate themes', () => {
    render(<DraftGenerator onGenerate={defaultOnGenerate} />);

    const input = screen.getByPlaceholderText(
      'Enter a theme and press Enter...'
    );

    fireEvent.change(input, { target: { value: 'robotics' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    fireEvent.change(input, { target: { value: 'robotics' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    const chips = screen.getAllByText('robotics');
    expect(chips).toHaveLength(1);
  });

  it('does not add empty or whitespace-only themes', () => {
    render(<DraftGenerator onGenerate={defaultOnGenerate} />);

    const input = screen.getByPlaceholderText(
      'Enter a theme and press Enter...'
    );

    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    expect(
      screen.getByText('Add at least one theme for the review')
    ).toBeInTheDocument();
  });

  it('shows the hint text when no themes are added', () => {
    render(<DraftGenerator onGenerate={defaultOnGenerate} />);

    expect(
      screen.getByText('Add at least one theme for the review')
    ).toBeInTheDocument();
  });

  it('defaults to academic style', () => {
    render(<DraftGenerator onGenerate={defaultOnGenerate} />);

    const input = screen.getByPlaceholderText(
      'Enter a theme and press Enter...'
    );
    fireEvent.change(input, { target: { value: 'test' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    const onGenerate = jest.fn();
    // Re-render with a fresh mock to check defaults
    const { unmount } = render(<DraftGenerator onGenerate={onGenerate} />);

    const inputNew = screen.getAllByPlaceholderText(
      'Enter a theme and press Enter...'
    )[1];
    fireEvent.change(inputNew, { target: { value: 'defaults' } });
    fireEvent.keyDown(inputNew, { key: 'Enter', code: 'Enter' });

    const generateButtons = screen.getAllByRole('button', {
      name: /generate literature review/i,
    });
    fireEvent.click(generateButtons[1]);

    const config: GenerationConfig = onGenerate.mock.calls[0][0];
    expect(config.style).toBe('academic');
    expect(config.maxSections).toBe(5);
    expect(config.includeAbstract).toBe(true);

    unmount();
  });

  it('displays max sections value in the label', () => {
    render(<DraftGenerator onGenerate={defaultOnGenerate} />);

    // Default maxSections is 5
    expect(screen.getByText('5')).toBeInTheDocument();
  });
});
