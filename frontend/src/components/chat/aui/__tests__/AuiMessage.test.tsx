import { describe, expect, it, vi } from 'vitest';
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { ChatRuntimeProvider } from '../ChatRuntimeProvider';
import {
  AuiMessages,
  AuiMessageByIndex,
  MessageByIndexBoundary,
} from '../AuiMessage';

const noop = vi.fn();

function Thrower({
  shouldThrow,
  message,
  children,
}: {
  shouldThrow: boolean;
  message: string;
  children?: React.ReactNode;
}): React.ReactElement {
  if (shouldThrow) throw new Error(message);
  return <>{children}</>;
}

function renderMessages(messages: ChatPageMessage[]) {
  return render(
    <ChatRuntimeProvider
      messages={messages}
      isRunning={false}
      onSend={noop}
      onCancel={noop}
    >
      <AuiMessages />
    </ChatRuntimeProvider>
  );
}

describe('AuiMessage', () => {
  it('renders user and assistant text parts through MessagePrimitive.Parts', () => {
    renderMessages([
      { id: 'u1', role: 'user', content: 'What is RAG?', timestamp: 1 },
      { id: 'a1', role: 'assistant', content: 'Retrieval augmented generation.', timestamp: 2 },
    ]);

    expect(screen.getByText('What is RAG?')).toBeInTheDocument();
    expect(screen.getByText('Retrieval augmented generation.')).toBeInTheDocument();
    expect(document.querySelector('[data-role="user"]')).toBeTruthy();
    expect(document.querySelector('[data-role="assistant"]')).toBeTruthy();
  });

  it('renders image and document attachments before user message parts', () => {
    renderMessages([
      {
        id: 'u1',
        role: 'user',
        content: 'Please inspect these.',
        timestamp: 1,
        attachments: [
          {
            id: 'img-1',
            document_id: 'doc-img',
            display_name: 'figure.png',
            thumbnail_url: 'https://example.test/figure.png',
            mime_type: 'image/png',
          },
          {
            id: 'doc-1',
            document_id: 'doc-pdf',
            document_title: 'paper.pdf',
            mime_type: 'application/pdf',
          },
        ],
      },
    ]);

    expect(screen.getByAltText('figure.png')).toHaveAttribute(
      'src',
      'https://example.test/figure.png'
    );
    expect(screen.getByText('paper.pdf')).toBeInTheDocument();
    expect(screen.getByText('PDF')).toBeInTheDocument();
  });

  it('renders tool-call parts with the shared ToolFallback UI', () => {
    renderMessages([
      {
        id: 'a1',
        role: 'assistant',
        content: 'Found two papers.',
        timestamp: 2,
        toolExecutions: [
          {
            tool: 'search_arxiv',
            label: 'Searching arXiv',
            status: 'done',
            argsSummary: 'query: rag',
            resultSummary: '2 papers',
          },
        ],
      },
    ]);

    expect(document.querySelector('[data-slot="tool-fallback-root"]')).toBeTruthy();
    expect(screen.getByText(/search_arxiv/)).toBeInTheDocument();
  });

  it('adds an autohiding action bar inside MessagePrimitive.Root for hover-driven controls', async () => {
    renderMessages([
      { id: 'a1', role: 'assistant', content: 'Copy me', timestamp: 2 },
    ]);

    const root = document.querySelector('[data-role="assistant"]');
    expect(root).toBeTruthy();
    fireEvent.mouseEnter(root as Element);

    const actionBar = await waitFor(() => {
      const node = document.querySelector('[data-slot="aui-message-actions"]');
      expect(node).toBeTruthy();
      return node;
    });
    expect(actionBar).toBeTruthy();
    expect(actionBar).toHaveAttribute('data-aui-autohide', 'always');
    expect(
      screen.getByRole('button', { name: /copy assistant message/i })
    ).toBeInTheDocument();
  });
});

describe('AuiAssistantMessage committed-path chrome (ChatBubble parity)', () => {
  function renderByIndex(
    messages: ChatPageMessage[],
    opts: {
      index?: number;
      onCitationClick?: (
        citations: unknown[],
        clicked: unknown,
        traceId?: string
      ) => void;
    } = {}
  ) {
    const index = opts.index ?? messages.length - 1;
    return render(
      <ChatRuntimeProvider
        messages={messages}
        isRunning={false}
        onSend={noop}
        onCancel={noop}
      >
        <AuiMessageByIndex
          index={index}
          message={messages[index]}
          onCitationClick={opts.onCitationClick as never}
        />
      </ChatRuntimeProvider>
    );
  }

  it('renders assistant markdown (bold), not raw asterisks', () => {
    renderByIndex([
      {
        id: 'a1',
        role: 'assistant',
        content: 'This is **important** context.',
        timestamp: 2,
      },
    ]);

    const strong = document.querySelector('strong');
    expect(strong).toBeTruthy();
    expect(strong?.textContent).toBe('important');
    expect(screen.queryByText(/\*\*important\*\*/)).not.toBeInTheDocument();
  });

  it('renders the tool strip with per-turn token usage and response time', () => {
    renderByIndex([
      {
        id: 'a1',
        role: 'assistant',
        content: 'Answer.',
        timestamp: 2,
        metadata: {
          responseTimeMs: 2300,
          tokenUsage: { input: 1234, output: 340 },
        },
      },
    ]);

    expect(screen.getByText('2.3s')).toBeInTheDocument();
    expect(screen.getByText(/1\.2k in/)).toBeInTheDocument();
    expect(screen.getByText(/340 out/)).toBeInTheDocument();
  });

  it('renders citation footer chips and forwards clicks', () => {
    const onCitationClick = vi.fn();
    renderByIndex(
      [
        {
          id: 'a1',
          role: 'assistant',
          content: 'Cited answer.',
          timestamp: 2,
          citations: [
            { documentId: 'd1', title: 'Attention Is All You Need', score: 0.92 },
          ],
        },
      ],
      { onCitationClick }
    );

    const chip = screen.getByText('Attention Is All You Need');
    expect(chip).toBeInTheDocument();
    expect(screen.getByText('92%')).toBeInTheDocument();
    fireEvent.click(chip.closest('button') as HTMLButtonElement);
    expect(onCitationClick).toHaveBeenCalledTimes(1);
  });

  it('renders the committed execution plan', () => {
    renderByIndex([
      {
        id: 'a1',
        role: 'assistant',
        content: 'Planned answer.',
        timestamp: 2,
        plan: [
          {
            step: 1,
            description: 'Search arXiv',
            tool: 'search_arxiv',
            args_hint: {},
            depends_on: [],
          },
        ],
      },
    ]);

    expect(screen.getByText('Execution plan')).toBeInTheDocument();
  });
});

describe('AuiMessageByIndex runtime-sync race', () => {
  it('renders nothing instead of throwing when the runtime thread is behind the list', () => {
    // The external-store runtime syncs post-commit (useEffect), so the list
    // can render an index the runtime doesn't have yet — e.g. thread switch
    // or first send. Regression: useClientLookup "Index 0 out of bounds".
    const staleMessage: ChatPageMessage = {
      id: 'a1',
      role: 'assistant',
      content: 'Not yet in runtime.',
      timestamp: 2,
    };

    expect(() =>
      render(
        <ChatRuntimeProvider
          messages={[]}
          isRunning={false}
          onSend={noop}
          onCancel={noop}
        >
          <AuiMessageByIndex index={0} message={staleMessage} />
        </ChatRuntimeProvider>
      )
    ).not.toThrow();

    expect(screen.queryByText('Not yet in runtime.')).not.toBeInTheDocument();
  });

  it('renders nothing instead of throwing when the runtime shrinks under a mounted message (thread switch)', () => {
    // Thread switch: the list mounts MessageByIndex(0) for thread A, then the
    // active thread's messages are cleared/replaced. The external-store runtime
    // syncs post-commit, so for one frame the runtime empties while the
    // still-mounted MessageByIndex(0) subscription re-reads its snapshot —
    // useClientLookup(0) on an empty thread. The render-time count guard cannot
    // catch this: the throw originates in the child's store-driven update, not
    // the parent's render. Prod crash: "useClientLookup: Index 0 out of bounds
    // (length: 0)" on thread switch.
    const msg: ChatPageMessage = {
      id: 'a1',
      role: 'assistant',
      content: 'From thread A.',
      timestamp: 2,
    };

    const { rerender } = render(
      <ChatRuntimeProvider
        messages={[msg]}
        isRunning={false}
        onSend={noop}
        onCancel={noop}
      >
        <AuiMessageByIndex index={0} message={msg} />
      </ChatRuntimeProvider>
    );
    expect(screen.getByText('From thread A.')).toBeInTheDocument();

    expect(() =>
      rerender(
        <ChatRuntimeProvider
          messages={[]}
          isRunning={false}
          onSend={noop}
          onCancel={noop}
        >
          <AuiMessageByIndex index={0} message={msg} />
        </ChatRuntimeProvider>
      )
    ).not.toThrow();

    expect(screen.queryByText('From thread A.')).not.toBeInTheDocument();
  });
});

describe('MessageByIndexBoundary', () => {
  // jsdom flushes too synchronously to reproduce the concurrent-scheduler torn
  // read that crashes prod on thread switch, so these test the boundary's
  // contract directly: it must swallow ONLY the transient out-of-bounds throw,
  // surface everything else, and re-attempt once the runtime settles.
  it('swallows the out-of-bounds throw and renders nothing', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() =>
      render(
        <MessageByIndexBoundary resetKey="a">
          <Thrower
            shouldThrow
            message="useClientLookup: Index 0 out of bounds (length: 0)"
          >
            should not render
          </Thrower>
        </MessageByIndexBoundary>
      )
    ).not.toThrow();
    expect(screen.queryByText('should not render')).not.toBeInTheDocument();
    spy.mockRestore();
  });

  it('rethrows non-out-of-bounds errors so real bugs surface', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() =>
      render(
        <MessageByIndexBoundary resetKey="a">
          <Thrower
            shouldThrow
            message="Cannot read properties of undefined (reading 'foo')"
          />
        </MessageByIndexBoundary>
      )
    ).toThrow(/Cannot read properties/);
    spy.mockRestore();
  });

  it('re-attempts rendering after the runtime settles (resetKey change)', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { rerender } = render(
      <MessageByIndexBoundary resetKey="a">
        <Thrower
          shouldThrow
          message="useClientLookup: Index 0 out of bounds (length: 0)"
        >
          recovered
        </Thrower>
      </MessageByIndexBoundary>
    );
    expect(screen.queryByText('recovered')).not.toBeInTheDocument();

    rerender(
      <MessageByIndexBoundary resetKey="b">
        <Thrower shouldThrow={false} message="unused">
          recovered
        </Thrower>
      </MessageByIndexBoundary>
    );
    expect(screen.getByText('recovered')).toBeInTheDocument();
    spy.mockRestore();
  });
});
