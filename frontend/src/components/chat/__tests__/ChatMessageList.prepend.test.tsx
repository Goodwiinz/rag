import { describe, expect, it, vi, beforeAll } from 'vitest';
import { render } from '@testing-library/react';

// The AUI message bubble needs a ThreadRuntime provider that jsdom lacks; the
// scroll-compensation logic under test is independent of bubble internals.
vi.mock('@/components/chat/aui/AuiMessage', () => ({
  AuiMessageByIndex: ({ index }: { index: number }) => (
    <div data-testid={`msg-${index}`} />
  ),
}));
vi.mock('@/components/chat/shared/InlineAgentSummary', () => ({
  InlineAgentSummary: () => null,
}));

import { ChatMessageList } from '@/components/chat/ChatMessageList';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';

beforeAll(() => {
  // jsdom lacks these
  Element.prototype.scrollIntoView = vi.fn();
  if (!('ResizeObserver' in globalThis)) {
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      }
    );
  }
});

const msg = (id: string, role: 'user' | 'assistant'): ChatPageMessage => ({
  id,
  role,
  content: `content ${id}`,
  timestamp: 1,
});

const baseProps = {
  activeThreadId: 't-1',
  isLoading: false,
  storeIsStreaming: false,
  storeStreamingContent: '',
  onRegenerate: vi.fn(),
  onCitationClick: vi.fn(),
  hasMore: true,
  isLoadingOlder: false,
  onLoadOlder: vi.fn(),
};

describe('ChatMessageList prepend scroll compensation', () => {
  it('offsets scrollTop by the scrollHeight delta when older messages are prepended', () => {
    const initial = [msg('m3', 'user'), msg('m4', 'assistant')];
    const { container, rerender } = render(
      <ChatMessageList {...baseProps} messages={initial} />
    );

    const scroller = container.querySelector(
      '[aria-label="Conversation transcript"]'
    ) as HTMLElement;
    expect(scroller).toBeTruthy();

    // Simulate layout: current content is 1000px tall, user sits at 100px.
    let scrollHeight = 1000;
    Object.defineProperty(scroller, 'scrollHeight', {
      configurable: true,
      get: () => scrollHeight,
    });
    scroller.scrollTop = 100;

    // Trigger a rerender so the layout effect records the 1000px baseline
    // (the effect also runs on mount, but scrollHeight was 0 then).
    rerender(<ChatMessageList {...baseProps} messages={[...initial]} />);

    // Prepend two older messages; the DOM "grows" to 1600px.
    scrollHeight = 1600;
    rerender(
      <ChatMessageList
        {...baseProps}
        messages={[msg('m1', 'user'), msg('m2', 'assistant'), ...initial]}
      />
    );

    // 100 + (1600 - 1000) = 700: the messages the user was reading stay put.
    expect(scroller.scrollTop).toBe(700);
  });

  it('does not touch scrollTop on an appended message', () => {
    const initial = [msg('m1', 'user')];
    const { container, rerender } = render(
      <ChatMessageList {...baseProps} messages={initial} />
    );
    const scroller = container.querySelector(
      '[aria-label="Conversation transcript"]'
    ) as HTMLElement;
    let scrollHeight = 500;
    Object.defineProperty(scroller, 'scrollHeight', {
      configurable: true,
      get: () => scrollHeight,
    });
    scroller.scrollTop = 100;
    rerender(<ChatMessageList {...baseProps} messages={[...initial]} />);

    scrollHeight = 800;
    rerender(
      <ChatMessageList
        {...baseProps}
        messages={[...initial, msg('m2', 'assistant')]}
      />
    );
    expect(scroller.scrollTop).toBe(100); // append → auto-scroll handles it, not us
  });
});
