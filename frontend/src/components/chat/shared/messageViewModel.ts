import type { Citation } from '@/utils/citationParser';

export interface ChatMessageViewModel {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  citations?: Citation[];
  modelName?: string;
  claims?: string[];
  confidence?: number;
  coverage?: number;
  decisionTraceId?: string;
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

export interface SearchResultChatMessageInput {
  query: string;
  answer: {
    text: string;
    sources: Array<{
      document_id: string;
      document_title: string;
      snippet: string;
      confidence: number;
      file_type?: string;
    }>;
    claims?: string[];
    confidence?: number;
    coverage?: number;
    decisionTraceId?: string;
    decision_trace_id?: string;
  };
}

export function mapChatMessageToViewModel(
  input: ChatRouteMessageInput
): ChatMessageViewModel {
  return { ...input };
}

function resolveDecisionTraceId(
  answer: SearchResultChatMessageInput['answer']
): string | undefined {
  if (answer.decisionTraceId) {
    return answer.decisionTraceId;
  }

  return answer.decision_trace_id;
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
  result: SearchResultChatMessageInput
): ChatMessageViewModel[] {
  const timestamp = Date.now();

  const userMessage: ChatMessageViewModel = {
    role: 'user',
    content: result.query,
    timestamp,
  };

  const assistantMessage: ChatMessageViewModel = {
    role: 'assistant',
    content: result.answer.text,
    timestamp,
    claims: result.answer.claims,
    confidence: result.answer.confidence,
    coverage: result.answer.coverage,
    decisionTraceId: resolveDecisionTraceId(result.answer),
    citations: result.answer.sources.map((source, index) => ({
      documentId: source.document_id,
      title: normalizeCitationTitle(source.document_title, index),
      score: source.confidence,
      content: source.snippet,
      source: source.file_type,
    })),
  };

  return [userMessage, assistantMessage];
}
