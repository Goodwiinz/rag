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
  diagnosticsTraceId?: string;
}

export interface ChatRouteMessageInput {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  citations?: Citation[];
  modelName?: string;
  diagnosticsTraceId?: string;
}

export function mapChatMessageToViewModel(
  input: ChatRouteMessageInput
): ChatMessageViewModel {
  return { ...input };
}

function normalizeCitationTitle(
  title: string | undefined,
  index: number
): string {
  const normalized = title?.replace(/\s+/g, ' ').trim() ?? '';

  if (!normalized) {
    return `Source ${index + 1}`;
  }

  const looksLikeTelemetry =
    /(message\s+body|verified\s+\d+\/?\d*|duration_ms|return\s+result|lambda)/i.test(
      normalized
    );

  if (looksLikeTelemetry) {
    return `Source ${index + 1}`;
  }

  return normalized.length > 120
    ? `${normalized.slice(0, 117)}...`
    : normalized;
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
    citations: result.answer.sources.map((source, index) => ({
      documentId: source.document_id,
      title: normalizeCitationTitle(source.document_title, index),
      score: source.confidence,
      content: source.snippet,
      source: source.file_type,
    })),
    diagnosticsTraceId: result.answer.decisionTraceId,
  };

  return [userMessage, assistantMessage];
}
