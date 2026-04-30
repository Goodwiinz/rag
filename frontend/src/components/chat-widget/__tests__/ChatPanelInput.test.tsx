import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@/test/test-utils';
import { ChatPanelInput } from '../ChatPanelInput';
import { expectNoA11yViolations } from '@/test/a11y';

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  Send: (props: React.SVGAttributes<SVGElement>) => (
    <svg data-testid="icon-send" {...props} />
  ),
}));

describe('ChatPanelInput', () => {
  const defaultProps = {
    value: '',
    onChange: vi.fn(),
    onSend: vi.fn(),
    disabled: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
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
    const onChange = vi.fn();
    render(<ChatPanelInput {...defaultProps} onChange={onChange} />);

    const textarea = screen.getByRole('textbox', {
      name: /chat message input/i,
    });
    fireEvent.change(textarea, { target: { value: 'test message' } });
    expect(onChange).toHaveBeenCalledWith('test message');
  });

  it('calls onSend when Enter pressed', () => {
    const onSend = vi.fn();
    render(<ChatPanelInput {...defaultProps} value="hello" onSend={onSend} />);

    const textarea = screen.getByRole('textbox', {
      name: /chat message input/i,
    });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    expect(onSend).toHaveBeenCalledTimes(1);
  });

  it('does not send on Shift+Enter', () => {
    const onSend = vi.fn();
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
    const onSend = vi.fn();
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

describe('ChatPanelInput a11y', () => {
  it('has no accessibility violations', async () => {
    const { container } = render(
      <ChatPanelInput
        value=""
        onChange={vi.fn()}
        onSend={vi.fn()}
        disabled={false}
      />
    );
    await expectNoA11yViolations(container);
  });
});
