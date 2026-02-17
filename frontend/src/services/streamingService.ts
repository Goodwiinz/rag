/**
 * Streaming Service
 *
 * Handles SSE (Server-Sent Events) streaming for chat messages.
 * Uses fetch + ReadableStream to consume streaming responses from the backend.
 *
 * Backend endpoint: POST /api/v2/threads/{threadId}/stream
 */

// ============================================================================
// Types
// ============================================================================

/** All possible SSE event types emitted by the streaming endpoint */
export type StreamEventType =
  | 'message_start'
  | 'rag_context'
  | 'token'
  | 'citation_inline'
  | 'message_done'
  | 'error';

/** A parsed SSE event with its type and payload */
export interface StreamEvent {
  type: StreamEventType;
  data: Record<string, unknown>;
}

/** Options for configuring the streaming chat request */
export interface StreamChatOptions {
  useRag?: boolean;
  temperature?: number;
  maxTokens?: number;
}

// ============================================================================
// SSE Parsing
// ============================================================================

/**
 * Parse a single SSE event line into a typed StreamEvent.
 *
 * @param eventType - The SSE event type (from the `event:` line)
 * @param dataStr - The raw data string (from the `data:` line)
 * @returns A StreamEvent if parsing succeeds, or null if the data is invalid JSON
 *          or not a plain object
 */
export function parseSSELine(
  eventType: StreamEventType,
  dataStr: string
): StreamEvent | null {
  try {
    const parsed: unknown = JSON.parse(dataStr);

    // Ensure parsed value is a plain object (not null, array, or primitive)
    if (
      typeof parsed !== 'object' ||
      parsed === null ||
      Array.isArray(parsed)
    ) {
      return null;
    }

    return {
      type: eventType,
      data: parsed as Record<string, unknown>,
    };
  } catch {
    return null;
  }
}

// ============================================================================
// Streaming Generator
// ============================================================================

/**
 * Async generator that streams chat messages from the backend via SSE.
 *
 * POSTs to `/api/v2/threads/{threadId}/stream` and yields typed StreamEvent
 * objects as they arrive. Supports cancellation via AbortSignal.
 *
 * @param threadId - The thread UUID to stream messages for
 * @param content - The user message content
 * @param options - Optional RAG and model configuration
 * @param signal - Optional AbortSignal for cancellation
 * @yields StreamEvent objects parsed from the SSE stream
 *
 * @example
 * ```ts
 * const controller = new AbortController();
 * for await (const event of streamChatMessage('thread-123', 'Hello', {}, controller.signal)) {
 *   if (event.type === 'token') {
 *     console.log(event.data.content);
 *   }
 * }
 * ```
 */
export async function* streamChatMessage(
  threadId: string,
  content: string,
  options?: StreamChatOptions,
  signal?: AbortSignal
): AsyncGenerator<StreamEvent> {
  const token = localStorage.getItem('auth-token');

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const body = JSON.stringify({
    content,
    ...(options?.useRag !== undefined && { use_rag: options.useRag }),
    ...(options?.temperature !== undefined && {
      temperature: options.temperature,
    }),
    ...(options?.maxTokens !== undefined && {
      max_tokens: options.maxTokens,
    }),
  });

  const response = await fetch(`/api/v2/threads/${threadId}/stream`, {
    method: 'POST',
    headers,
    body,
    signal,
  });

  if (!response.ok) {
    const message = await response.text();
    yield {
      type: 'error',
      data: {
        code: `http_${response.status}`,
        message,
      },
    };
    return;
  }

  if (!response.body) {
    yield {
      type: 'error',
      data: {
        code: 'no_body',
        message: 'Response body is empty',
      },
    };
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let currentEventType: StreamEventType | null = null;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Process complete lines from the buffer
      const lines = buffer.split('\n');
      // Keep the last (potentially incomplete) line in the buffer
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        const trimmed = line.trim();

        if (trimmed.startsWith('event: ')) {
          currentEventType = trimmed.slice(7).trim() as StreamEventType;
        } else if (trimmed.startsWith('data: ') && currentEventType) {
          const dataStr = trimmed.slice(6);
          const event = parseSSELine(currentEventType, dataStr);
          if (event) {
            yield event;
          }
          currentEventType = null;
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
