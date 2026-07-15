import { describe, expect, it, vi } from 'vitest';
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useThread, useThreadRuntime } from '@assistant-ui/react';

import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { makeChatPageMessage } from '@/test/chatMessageFactory';
import { ChatRuntimeProvider } from '../ChatRuntimeProvider';

const messages: ChatPageMessage[] = [
  makeChatPageMessage({ id: 'u1', role: 'user', content: 'hi', timestamp: 1 }),
  makeChatPageMessage({
    id: 'a1',
    role: 'assistant',
    content: 'hello',
    timestamp: 2,
  }),
];

function Probe() {
  const msgCount = useThread((t) => t.messages.length);
  const running = useThread((t) => t.isRunning);
  return (
    <div data-testid="probe">
      {msgCount}:{String(running)}
    </div>
  );
}

function IdentityProbe() {
  const ids = useThread((thread) =>
    thread.messages.map((message) => message.id).join(',')
  );
  return <div data-testid="identity-probe">{ids}</div>;
}

function CancelProbe() {
  const runtime = useThreadRuntime();
  return (
    <button type="button" onClick={() => runtime.cancelRun()}>
      cancel
    </button>
  );
}

describe('ChatRuntimeProvider', () => {
  it('projects messages and isRunning into the assistant-ui thread', () => {
    render(
      <ChatRuntimeProvider
        messages={messages}
        isRunning
        onSend={vi.fn()}
        onCancel={vi.fn()}
      >
        <Probe />
      </ChatRuntimeProvider>
    );

    expect(screen.getByTestId('probe')).toHaveTextContent('2:true');
  });

  it('invokes onCancel when the runtime cancels a run', async () => {
    const onCancel = vi.fn();
    const user = userEvent.setup();
    render(
      <ChatRuntimeProvider
        messages={messages}
        isRunning
        onSend={vi.fn()}
        onCancel={onCancel}
      >
        <CancelProbe />
      </ChatRuntimeProvider>
    );

    await user.click(screen.getByRole('button', { name: 'cancel' }));

    await waitFor(() => expect(onCancel).toHaveBeenCalledTimes(1));
  });

  it('keeps the runtime identity stable when an optimistic row becomes canonical', async () => {
    const optimistic = makeChatPageMessage({
      runtimeId: 'runtime-turn-1',
      source: 'optimistic',
      role: 'assistant',
      content: 'Persisted answer',
      timestamp: 2,
    });
    const canonical = makeChatPageMessage({
      id: 'db-message-1',
      runtimeId: 'runtime-turn-1',
      source: 'canonical',
      role: 'assistant',
      content: 'Persisted answer',
      timestamp: 2,
    });

    const { rerender } = render(
      <ChatRuntimeProvider
        messages={[optimistic]}
        isRunning={false}
        onSend={vi.fn()}
        onCancel={vi.fn()}
      >
        <IdentityProbe />
      </ChatRuntimeProvider>
    );
    expect(screen.getByTestId('identity-probe')).toHaveTextContent(
      'runtime-turn-1'
    );

    rerender(
      <ChatRuntimeProvider
        messages={[canonical]}
        isRunning={false}
        onSend={vi.fn()}
        onCancel={vi.fn()}
      >
        <IdentityProbe />
      </ChatRuntimeProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('identity-probe')).toHaveTextContent(
        'runtime-turn-1'
      )
    );
    expect(screen.getByTestId('identity-probe')).not.toHaveTextContent(
      'db-message-1'
    );
  });
});
