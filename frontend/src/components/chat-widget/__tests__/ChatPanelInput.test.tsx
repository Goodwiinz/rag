import { render, screen, fireEvent } from '@testing-library/react';
import { ChatPanelInput } from '../ChatPanelInput';

// Mock lucide-react icons
jest.mock('lucide-react', () => ({
  Send: (props: React.SVGAttributes<SVGElement>) => (
    <svg data-testid="icon-send" {...props} />
  ),
}));

describe('ChatPanelInput', () => {
  const defaultProps = {
    value: '',
    onChange: jest.fn(),
    onSend: jest.fn(),
    disabled: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders input field and send button', () => {
    render(<ChatPanelInput {...defaultProps} />);
    expect(
      screen.getByRole('textbox', { name: /chat message input/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /send message/i })
    ).toBeInTheDocument();
  });

  it('calls onChange when typing', () => {
    const onChange = jest.fn();
    render(<ChatPanelInput {...defaultProps} onChange={onChange} />);

    const textarea = screen.getByRole('textbox', {
      name: /chat message input/i,
    });
    fireEvent.change(textarea, { target: { value: 'test message' } });
    expect(onChange).toHaveBeenCalledWith('test message');
  });

  it('calls onSend when Enter pressed', () => {
    const onSend = jest.fn();
    render(<ChatPanelInput {...defaultProps} value="hello" onSend={onSend} />);

    const textarea = screen.getByRole('textbox', {
      name: /chat message input/i,
    });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    expect(onSend).toHaveBeenCalledTimes(1);
  });

  it('does not send on Shift+Enter', () => {
    const onSend = jest.fn();
    render(<ChatPanelInput {...defaultProps} value="hello" onSend={onSend} />);

    const textarea = screen.getByRole('textbox', {
      name: /chat message input/i,
    });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
  });

  it('send button disabled when input empty', () => {
    render(<ChatPanelInput {...defaultProps} value="" />);
    const sendButton = screen.getByRole('button', { name: /send message/i });
    expect(sendButton).toBeDisabled();
  });

  it('send button disabled when streaming', () => {
    render(<ChatPanelInput {...defaultProps} value="hello" disabled={true} />);
    const sendButton = screen.getByRole('button', { name: /send message/i });
    expect(sendButton).toBeDisabled();
  });

  it('does not call onSend when disabled', () => {
    const onSend = jest.fn();
    render(
      <ChatPanelInput
        {...defaultProps}
        value="hello"
        onSend={onSend}
        disabled={true}
      />
    );

    const textarea = screen.getByRole('textbox', {
      name: /chat message input/i,
    });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    expect(onSend).not.toHaveBeenCalled();
  });
});
