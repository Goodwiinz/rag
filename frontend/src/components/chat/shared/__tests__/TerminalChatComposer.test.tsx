import { fireEvent, render, screen } from '@testing-library/react';
import { TerminalChatComposer } from '../TerminalChatComposer';

describe('TerminalChatComposer', () => {
  it('submits on Enter without Shift', () => {
    const onSubmit = jest.fn();

    render(
      <TerminalChatComposer
        value="hello"
        onChange={jest.fn()}
        onSubmit={onSubmit}
        onStop={jest.fn()}
        isLoading={false}
      />
    );

    fireEvent.keyDown(screen.getByPlaceholderText(/inject query/i), {
      key: 'Enter',
    });

    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it('does not submit on Shift+Enter', () => {
    const onSubmit = jest.fn();

    render(
      <TerminalChatComposer
        value="hello"
        onChange={jest.fn()}
        onSubmit={onSubmit}
        onStop={jest.fn()}
        isLoading={false}
      />
    );

    fireEvent.keyDown(screen.getByPlaceholderText(/inject query/i), {
      key: 'Enter',
      shiftKey: true,
    });

    expect(onSubmit).not.toHaveBeenCalled();
  });
});

