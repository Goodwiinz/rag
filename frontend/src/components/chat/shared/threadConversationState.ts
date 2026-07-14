import type { Thread } from '@/types/workspace';

export interface ConversationStateMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

export interface ConversationStateItem {
  id: string;
  title: string;
  messages: ConversationStateMessage[];
  createdAt: number;
  updatedAt: number;
  threadId: string;
  conversationId: string;
  previewText?: string;
  messageCount?: number;
}

export function upsertConversationFromThread<T extends ConversationStateItem>(
  conversations: T[],
  thread: Thread,
  messages: ConversationStateMessage[] = []
): T[] {
  const nextConversation = {
    id: thread.id,
    title: thread.title || 'New Chat',
    messages,
    createdAt: new Date(thread.created_at).getTime(),
    updatedAt: new Date(thread.updated_at).getTime(),
    threadId: thread.id,
    conversationId: thread.conversation_id,
    previewText:
      messages[messages.length - 1]?.content ??
      thread.last_message_preview ??
      thread.summary ??
      undefined,
    messageCount: thread.message_count,
  } as T;

  const existingIndex = conversations.findIndex(
    (conversation) => conversation.id === thread.id
  );

  if (existingIndex === -1) {
    return [nextConversation, ...conversations];
  }

  return conversations.map((conversation, index) =>
    index === existingIndex
      ? { ...conversation, ...nextConversation }
      : conversation
  );
}
