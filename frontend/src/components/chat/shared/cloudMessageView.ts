import { MessageRole, type ChatMessage } from '@/types/workspace';
import { normalizeCitation } from '@/utils/citationNormalizer';
import type { Citation } from '@/utils/citationParser';

export interface ChatPageMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  citations?: Citation[];
  diagnosticsTraceId?: string;
  metadata?: {
    toolsUsed?: string[];
    responseTimeMs?: number;
    sourcesCount?: number;
  };
}

export function mapStoreMessagesToChatMessages(
  messages: ChatMessage[]
): ChatPageMessage[] {
  return messages.map((dbMsg) => ({
    id: dbMsg.id,
    role: dbMsg.role === MessageRole.USER ? 'user' : 'assistant',
    content: dbMsg.content,
    timestamp: new Date(dbMsg.created_at).getTime(),
    citations: dbMsg.citations?.map(normalizeCitation),
    metadata: dbMsg.latency_ms
      ? { responseTimeMs: dbMsg.latency_ms }
      : undefined,
  }));
}

interface SelectDisplayedMessagesParams {
  localMessages: ChatPageMessage[];
  storeMessages?: ChatMessage[];
}

function shouldUseStoreMessages(
  localMessages: ChatPageMessage[],
  storeMessages: ChatMessage[]
): boolean {
  return (
    storeMessages.length > 0 && storeMessages.length >= localMessages.length
  );
}

export function selectDisplayedMessages({
  localMessages,
  storeMessages = [],
}: SelectDisplayedMessagesParams): ChatPageMessage[] {
  if (shouldUseStoreMessages(localMessages, storeMessages)) {
    return mapStoreMessagesToChatMessages(storeMessages);
  }

  return localMessages;
}

interface ConversationWithMessages {
  id: string;
  messages: ChatPageMessage[];
  updatedAt: number;
  previewText?: string;
  messageCount?: number;
}

function messagesMatch(
  left: ChatPageMessage[],
  right: ChatPageMessage[]
): boolean {
  return (
    left.length === right.length &&
    left.every((message, index) => {
      const other = right[index];
      return (
        message.id === other?.id &&
        message.role === other?.role &&
        message.content === other?.content &&
        message.timestamp === other?.timestamp
      );
    })
  );
}

export function syncConversationMessagesWithStore<
  T extends ConversationWithMessages,
>(
  conversations: T[],
  threadId: string | null | undefined,
  storeMessages: ChatMessage[] = []
): T[] {
  if (!threadId || storeMessages.length === 0) {
    return conversations;
  }

  const mappedMessages = mapStoreMessagesToChatMessages(storeMessages);

  return conversations.map((conversation) => {
    if (conversation.id !== threadId) {
      return conversation;
    }

    if (mappedMessages.length < conversation.messages.length) {
      return conversation;
    }

    if (messagesMatch(conversation.messages, mappedMessages)) {
      return conversation;
    }

    return {
      ...conversation,
      messages: mappedMessages,
      previewText: mappedMessages[mappedMessages.length - 1]?.content,
      messageCount: Math.max(
        conversation.messageCount ?? 0,
        mappedMessages.length
      ),
      updatedAt:
        mappedMessages[mappedMessages.length - 1]?.timestamp ??
        conversation.updatedAt,
    };
  });
}
