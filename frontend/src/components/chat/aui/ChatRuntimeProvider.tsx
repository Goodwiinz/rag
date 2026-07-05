'use client';

import { type ReactElement, type ReactNode, useCallback } from 'react';
import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
} from '@assistant-ui/react';

import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';

import { convertMessage } from './convertMessage';

export interface ChatRuntimeProviderProps {
  messages: ChatPageMessage[];
  isRunning: boolean;
  /** When true, the composer refuses to send (e.g. a HITL confirmation
   * is pending). Passed through to the runtime's compose disabled state. */
  isSendDisabled?: boolean;
  /** Delegates to the existing useChatStreaming send. Required by the
   * external-store API even though the composer stays custom in stage 1. */
  onSend: (text: string) => void;
  onCancel: () => void;
  children: ReactNode;
}

/**
 * Projects the existing /chat page state into an assistant-ui
 * ExternalStoreRuntime. The runtime never owns state — it is a pure
 * projection of the props; sends and cancels delegate back to the
 * existing streaming hooks.
 */
export function ChatRuntimeProvider({
  messages,
  isRunning,
  isSendDisabled,
  onSend,
  onCancel,
  children,
}: ChatRuntimeProviderProps): ReactElement {
  const onNew = useCallback(
    async (message: AppendMessage) => {
      const text = message.content
        .filter((p): p is { type: 'text'; text: string } => p.type === 'text')
        .map((p) => p.text)
        .join('\n');
      // Guard against empty sends (whitespace-only / no text parts) — the
      // composer should never emit these, but the runtime is a pure
      // projection and should not call onSend with an empty string.
      if (!text) return;
      onSend(text);
    },
    [onSend]
  );

  const handleCancel = useCallback(async () => {
    onCancel();
  }, [onCancel]);

  const runtime = useExternalStoreRuntime({
    messages,
    isRunning,
    isSendDisabled,
    convertMessage,
    onNew,
    onCancel: handleCancel,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  );
}
