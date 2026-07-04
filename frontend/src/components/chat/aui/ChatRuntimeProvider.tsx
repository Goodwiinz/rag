'use client';

import { type ReactElement, type ReactNode, useCallback } from 'react';
import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
} from '@assistant-ui/react';

import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';

import { convertMessage } from './convertMessage';

interface ChatRuntimeProviderProps {
  messages: ChatPageMessage[];
  isRunning: boolean;
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
  onSend,
  onCancel,
  children,
}: ChatRuntimeProviderProps): ReactElement {
  const onNew = useCallback(
    async (message: AppendMessage) => {
      const text = message.content
        .filter(
          (p): p is { type: 'text'; text: string } => p.type === 'text'
        )
        .map((p) => p.text)
        .join('\n');
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
