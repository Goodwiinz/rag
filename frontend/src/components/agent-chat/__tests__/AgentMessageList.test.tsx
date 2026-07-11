import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { AgentMessage } from '@/types/agent-chat';
import { useAgentChatStore } from '@/store/agentChatStore';
import { AgentMessageList } from '../AgentMessageList';

vi.mock('../AgentMessageItem', () => ({
  AgentMessageItem: ({ message }: { message: AgentMessage }) => (
    <div>{message.content}</div>
  ),
}));

vi.mock('../ConfirmationCard', () => ({
  ConfirmationCard: () => null,
}));

const assistant = (content: string): AgentMessage => ({
  id: 'assistant-1',
  role: 'assistant',
  content,
  timestamp: new Date(),
  isStreaming: true,
});

describe('AgentMessageList', () => {
  beforeEach(() => {
    useAgentChatStore.getState().reset();
    Object.defineProperty(HTMLElement.prototype, 'scrollTo', {
      configurable: true,
      value: vi.fn(),
    });
  });

  it('follows streamed content updates without waiting for another message', () => {
    const scrollTo = HTMLElement.prototype.scrollTo as unknown as ReturnType<typeof vi.fn>;
    const { container, rerender } = render(
      <AgentMessageList messages={[assistant('first token')]} isStreaming />
    );
    const scroller = container.querySelector('.overflow-y-auto') as HTMLDivElement;
    Object.defineProperty(scroller, 'scrollHeight', {
      configurable: true,
      value: 500,
    });
    scrollTo.mockClear();

    rerender(
      <AgentMessageList messages={[assistant('first token, second token')]} isStreaming />
    );

    expect(scrollTo).toHaveBeenCalledWith({ top: 500, behavior: 'auto' });
  });

  it('shows a loading state instead of the prior transcript while a thread loads', () => {
    useAgentChatStore.setState({ isLoadingMessages: true });

    render(<AgentMessageList messages={[]} isStreaming={false} />);

    expect(screen.getByRole('status')).toHaveTextContent('Loading conversation');
  });
});
