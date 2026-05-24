'use client';

import { cn } from '@/lib/utils';
import { getReferencedCitations, type Citation } from '@/utils/citationParser';
import { Activity, Check, Copy, RefreshCw } from 'lucide-react';
import { useMemo, useState } from 'react';
import { CitationRenderer } from '../CitationRenderer';

export interface ChatBubbleMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  citations?: Citation[];
  diagnosticsTraceId?: string;
}

export interface ChatBubbleProps {
  message: ChatBubbleMessage;
  index: number;
  modelName?: string;
  isTyping?: boolean;
  isStreaming?: boolean;
  streamingContent?: string;
  onRetry?: () => void;
  onCitationClick?: (citations: Citation[], clickedCitation: Citation) => void;
}

export function ChatBubble({
  message,
  index: _index,
  modelName,
  isTyping,
  isStreaming,
  streamingContent,
  onRetry,
  onCitationClick,
}: ChatBubbleProps) {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);

  const timestamp = message.timestamp
    ? new Date(message.timestamp).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      })
    : '--:--';

  const handleCopy = async () => {
    try {
      const textToCopy = streamingContent || message.content;
      if (!textToCopy) return;
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard access denied or page unfocused
    }
  };

  const visibleCitations = useMemo(
    () => getReferencedCitations(message.content, message.citations ?? []),
    [message.content, message.citations]
  );

  return (
    <div
      className={cn(
        'group relative mb-4 sm:mb-5',
        isUser ? 'ml-4 sm:ml-16' : 'mr-4 sm:mr-16'
      )}
    >
      {/* Meta row */}
      <div
        className={cn(
          'mb-1.5 flex items-center gap-2 text-[11px]',
          isUser ? 'justify-end pr-1' : 'pl-1'
        )}
        style={{ fontFamily: 'var(--nous-font-ui)' }}
      >
        {!isUser && (
          <>
            {(isStreaming || isTyping) && (
              <span className="text-[10px] font-medium text-[var(--nous-sol)] animate-pulse">
                {isStreaming ? 'Streaming' : 'Thinking'}
              </span>
            )}
            {modelName && (
              <span className="text-[var(--nous-fg-3)] text-[10px]">
                {modelName}
              </span>
            )}
          </>
        )}
        <span className="text-[var(--nous-fg-3)]">{timestamp}</span>

        <div className="flex items-center gap-0.5 opacity-0 transition-all duration-200 group-hover:opacity-100 touch-show">
          <button
            onClick={handleCopy}
            className={cn(
              'rounded-lg p-2 sm:p-1.5 transition-all hover:bg-[var(--nous-sol)]/8',
              copied
                ? 'text-[var(--nous-terra)]'
                : 'text-[var(--nous-fg-3)] hover:text-[var(--nous-fg-1)]'
            )}
            aria-label={copied ? 'Copied!' : 'Copy message'}
            title={copied ? 'Copied!' : 'Copy message'}
          >
            {copied ? (
              <Check className="h-4 w-4 sm:h-3.5 sm:w-3.5" />
            ) : (
              <Copy className="h-4 w-4 sm:h-3.5 sm:w-3.5" />
            )}
          </button>
          {message.role === 'assistant' && onRetry && (
            <button
              onClick={onRetry}
              className="rounded-lg p-2 sm:p-1.5 text-[var(--nous-fg-3)] transition-all hover:bg-[var(--nous-sol)]/8 hover:text-[var(--nous-fg-1)]"
              aria-label="Regenerate response"
              title="Regenerate response"
            >
              <RefreshCw className="h-4 w-4 sm:h-3.5 sm:w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Bubble */}
      <div
        className={cn(
          'relative overflow-hidden rounded-2xl transition-all duration-200',
          isUser
            ? 'nous-bubble-user'
            : 'nous-bubble-assistant hover:border-[var(--nous-sol)]/20'
        )}
      >
        <div className="relative z-10 p-3.5 sm:p-5 overflow-hidden break-words">
          {isStreaming && !streamingContent ? (
            <div className="nous-chat-body">
              <span
                className="ml-0.5 inline-block h-4 w-[3px] rounded-sm animate-pulse bg-[var(--nous-sol)]"
                data-testid="streaming-cursor"
              />
            </div>
          ) : isStreaming && streamingContent ? (
            <div className="nous-chat-body">
              <span className="whitespace-pre-wrap">{streamingContent}</span>
              <span
                className="ml-0.5 inline-block h-4 w-[3px] rounded-sm animate-pulse bg-[var(--nous-sol)]"
                data-testid="streaming-cursor"
              />
            </div>
          ) : isTyping && !message.content ? (
            <div
              className="flex items-center gap-3 text-sm text-[var(--nous-sol)]"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              <div className="flex items-center gap-1.5">
                <span
                  className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--nous-sol)]"
                  style={{ animationDelay: '0ms' }}
                />
                <span
                  className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--nous-sol)]/70"
                  style={{ animationDelay: '150ms' }}
                />
                <span
                  className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--nous-sol)]/40"
                  style={{ animationDelay: '300ms' }}
                />
              </div>
              <span className="text-[11px] font-medium text-[var(--nous-fg-3)]">
                Thinking…
              </span>
            </div>
          ) : (
            <div
              className={cn(
                'nous-chat-body',
                isUser && 'text-[var(--nous-erebus)]'
              )}
            >
              {isUser ? (
                <p className="whitespace-pre-wrap">{message.content}</p>
              ) : (
                <CitationRenderer
                  content={message.content}
                  citations={message.citations as Citation[]}
                  onCitationClick={(citation) => {
                    if (onCitationClick) {
                      onCitationClick(visibleCitations, citation);
                    }
                  }}
                />
              )}
            </div>
          )}
        </div>

        {/* Citations footer */}
        {!isUser && visibleCitations.length > 0 && (
          <div className="relative border-t border-[var(--nous-border-1)] bg-[var(--nous-bg-1)]/50 p-3">
            <div className="flex flex-wrap items-center gap-2">
              {visibleCitations.map((citation, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    if (onCitationClick) {
                      onCitationClick(visibleCitations, citation);
                    }
                  }}
                  className="group/citation flex items-center gap-2 rounded-lg border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] px-2.5 py-1.5 text-[10px] transition-all hover:border-[var(--nous-sol)]/30 hover:bg-[var(--nous-sol)]/5"
                  style={{ fontFamily: 'var(--nous-font-mono)' }}
                >
                  <div className="h-1.5 w-1.5 rounded-full bg-[var(--nous-sol)]/30 transition-colors group-hover/citation:bg-[var(--nous-sol)]" />
                  <span className="max-w-[180px] truncate text-[var(--nous-fg-1)]">
                    {citation.title}
                  </span>
                  <span className="border-l border-[var(--nous-border-1)] pl-2 text-[var(--nous-fg-3)]">
                    {Math.round(citation.score * 100)}%
                  </span>
                </button>
              ))}
              {message.diagnosticsTraceId && (
                <a
                  href={`/diagnostics?trace=${encodeURIComponent(message.diagnosticsTraceId)}`}
                  className="ml-auto flex items-center gap-1 rounded-lg border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] px-2 py-1 text-[9px] text-[var(--nous-fg-3)] transition-all hover:border-[var(--nous-sol)]/30 hover:text-[var(--nous-sol)]"
                  style={{ fontFamily: 'var(--nous-font-mono)' }}
                  title="View retrieval diagnostics"
                >
                  <Activity className="h-3 w-3" />
                  <span>DIAG</span>
                </a>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ChatBubble;
