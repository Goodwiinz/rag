import type { SearchResult } from '@/types/search';
import type { Citation } from '@/utils/citationParser';

export interface ChatMessageViewModel {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  citations?: Citation[];
  modelName?: string;
  isStreaming?: boolean;
  streamingContent?: string;
}

export interface ChatRouteMessageInput {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  citations?: Citation[];
  modelName?: string;
}

export function mapChatMessageToViewModel(
  input: ChatRouteMessageInput
): ChatMessageViewModel {
  return { ...input };
}

export function mapSearchResultToChatMessages(
  result: SearchResult
): ChatMessageViewModel[] {
  const userMessage: ChatMessageViewModel = {
    role: 'user',
    content: result.query,
    timestamp: Date.now(),
  };

  const assistantMessage: ChatMessageViewModel = {
    role: 'assistant',
    content: result.answer.text,
    timestamp: Date.now(),
    citations: result.answer.sources.map((source) => ({
      documentId: source.document_id,
      title: source.document_title,
      score: source.confidence,
      content: source.snippet,
      source: source.file_type,
    })),
  };

  return [userMessage, assistantMessage];
}

