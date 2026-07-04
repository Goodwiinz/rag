import { describe, expect, it, vi } from 'vitest';
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useThread, useThreadRuntime } from '@assistant-ui/react';

import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { ChatRuntimeProvider } from '../ChatRuntimeProvider';

const messages: ChatPageMessage[] = [
  { id: 'u1', role: 'user', content: 'hi', timestamp: 1 },
  { id: 'a1', role: 'assistant', content: 'hello', timestamp: 2 },
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
});
