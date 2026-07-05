'use client';

import {
  AssistantRuntimeProvider,
  type AppendMessage,
  type ThreadMessageLike,
  useExternalStoreRuntime,
} from '@assistant-ui/react';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import React, { useCallback } from 'react';

interface ChatAssistantRuntimeProviderProps {
  children: React.ReactNode;
  messages: ChatPageMessage[];
  isRunning: boolean;
  isSendDisabled?: boolean;
  onNew: (content: string) => Promise<void> | void;
}

function appendMessageText(message: AppendMessage): string {
  return message.content
    .filter((part) => part.type === 'text')
    .map((part) => part.text)
    .join('\n')
    .trim();
}

function convertMessage(message: ChatPageMessage): ThreadMessageLike {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    createdAt: message.timestamp ? new Date(message.timestamp) : undefined,
  };
}

export function ChatAssistantRuntimeProvider({
  children,
  messages,
  isRunning,
  isSendDisabled,
  onNew,
}: ChatAssistantRuntimeProviderProps) {
  const handleNew = useCallback(
    async (message: AppendMessage) => {
      const content = appendMessageText(message);
      if (!content) return;
      await onNew(content);
    },
    [onNew]
  );

  const runtime = useExternalStoreRuntime({
    messages,
    isRunning,
    isSendDisabled,
    convertMessage,
    onNew: handleNew,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  );
}
