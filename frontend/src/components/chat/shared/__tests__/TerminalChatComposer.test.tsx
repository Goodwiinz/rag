import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { TerminalChatComposer } from '../TerminalChatComposer';

describe('TerminalChatComposer', () => {
  it('submits on Enter without Shift', () => {
    const onSubmit = vi.fn();

    render(
      <TerminalChatComposer
        value="hello"
        onChange={vi.fn()}
        onSubmit={onSubmit}
        onStop={vi.fn()}
        isLoading={false}
      />
    );

    fireEvent.keyDown(screen.getByPlaceholderText(/message nous/i), {
      key: 'Enter',
    });

    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it('does not submit on Shift+Enter', () => {
    const onSubmit = vi.fn();

    render(
      <TerminalChatComposer
        value="hello"
        onChange={vi.fn()}
        onSubmit={onSubmit}
        onStop={vi.fn()}
        isLoading={false}
      />
    );

    fireEvent.keyDown(screen.getByPlaceholderText(/message nous/i), {
      key: 'Enter',
      shiftKey: true,
    });

    expect(onSubmit).not.toHaveBeenCalled();
  });
});

