import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';

export interface ChatConversation {
  id: string;
  title: string;
  messages: ChatPageMessage[];
  modelId?: string;
  createdAt: number;
  updatedAt: number;
  threadId: string;
  conversationId: string;
  previewText?: string;
  messageCount?: number;
}

export function generateConversationTitle(message: string): string {
  let title = message.trim();

  const prefixesToRemove = [
    /^(hi|hello|hey|good morning|good afternoon|good evening)[,!\s]*/i,
    /^(can you|could you|would you|please|i need|i want|i'd like)[,\s]*/i,
    /^(help me|assist me|tell me|show me|explain)[,\s]*/i,
  ];

  for (const prefix of prefixesToRemove) {
    title = title.replace(prefix, '');
  }

  title = title.charAt(0).toUpperCase() + title.slice(1);

  if (title.length > 40) {
    const truncated = title.substring(0, 40);
    const lastSpace = truncated.lastIndexOf(' ');
    if (lastSpace > 20) {
      title = truncated.substring(0, lastSpace) + '...';
    } else {
      title = truncated + '...';
    }
  }

  if (title.length < 3) {
    title = message.trim().substring(0, 40);
    if (message.length > 40) title += '...';
  }

  return title;
}
