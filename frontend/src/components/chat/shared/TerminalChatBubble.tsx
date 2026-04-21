'use client';

import { cn } from '@/lib/utils';
import { getReferencedCitations, type Citation } from '@/utils/citationParser';
import { Activity, Check, Copy, RefreshCw } from 'lucide-react';
import { useMemo, useState } from 'react';
import { CitationRenderer } from '../CitationRenderer';

export interface TerminalChatBubbleMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  citations?: Citation[];
  diagnosticsTraceId?: string;
}

export interface TerminalChatBubbleProps {
  message: TerminalChatBubbleMessage;
  index: number;
  modelName?: string;
  isTyping?: boolean;
  isStreaming?: boolean;
  streamingContent?: string;
  onRetry?: () => void;
  onCitationClick?: (citations: Citation[], clickedCitation: Citation) => void;
}

export function TerminalChatBubble({
  message,
  index: _index,
  modelName,
  isTyping,
  isStreaming,
  streamingContent,
  onRetry,
  onCitationClick,
}: TerminalChatBubbleProps) {
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
        'group relative mb-4',
        isUser ? 'ml-4 sm:ml-10' : 'mr-4 sm:mr-10'
      )}
    >
      <div
        className={cn(
          'absolute top-0 h-full w-[1px] opacity-30',
          isUser
            ? 'right-0 bg-gradient-to-b from-[var(--amber-gold)] via-[var(--amber-gold)]/10 to-transparent'
            : 'left-0 bg-gradient-to-b from-[var(--phosphor-green)] via-[var(--phosphor-green)]/10 to-transparent'
        )}
      />

      <div
        className={cn(
          'mb-2 flex items-center gap-3 text-[11px] tracking-wide',
          isUser ? 'justify-end pr-4' : 'pl-4'
        )}
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        {!isUser && (
          <>
            <div className="rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)] px-2 py-0.5">
              <span className="text-[10px] font-bold text-[var(--phosphor-green)]">
                {isStreaming
                  ? 'STREAMING'
                  : isTyping
                    ? 'PROCESSING'
                    : 'RECEIVED'}
              </span>
            </div>
            {modelName && (
              <span className="rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)] px-2 py-0.5 text-[var(--terminal-text-dim)]/90">
                {modelName}
              </span>
            )}
          </>
        )}
        {isUser && (
          <span className="rounded border border-[var(--amber-gold)]/20 bg-[var(--amber-gold)]/10 px-2 py-0.5 text-[10px] font-bold text-[var(--amber-gold)]">
            QUERY
          </span>
        )}
        <span className="text-[var(--terminal-text-dim)]/90">{timestamp}</span>

        <div className="flex items-center gap-1 opacity-0 transition-all duration-200 group-hover:opacity-100">
          <button
            onClick={handleCopy}
            className={cn(
              'rounded border border-transparent p-1 transition-all hover:border-[var(--terminal-border)] hover:bg-[var(--terminal-elevated)]',
              copied
                ? 'text-[var(--phosphor-green)]'
                : 'text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)]'
            )}
            aria-label={copied ? 'Copied!' : 'Copy message'}
            title={copied ? 'Copied!' : 'Copy message'}
          >
            {copied ? (
              <Check className="h-3.5 w-3.5" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
          </button>
          {message.role === 'assistant' && onRetry && (
            <button
              onClick={onRetry}
              className="rounded border border-transparent p-1 text-[var(--terminal-text-dim)] transition-all hover:border-[var(--terminal-border)] hover:bg-[var(--terminal-elevated)] hover:text-[var(--terminal-text)]"
              aria-label="Regenerate response"
              title="Regenerate response"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      <div
        className={cn(
          'relative overflow-hidden rounded-xl border transition-colors duration-200',
          isUser
            ? 'mr-4 border-[var(--amber-gold)]/15 bg-[var(--terminal-surface)] hover:border-[var(--amber-gold)]/30'
            : 'ml-4 border-[var(--terminal-border)] bg-[var(--terminal-surface)] hover:border-[var(--phosphor-green)]/25'
        )}
      >

        <div className="relative z-10 p-4 sm:p-5 overflow-hidden break-words">
          {isStreaming && !streamingContent ? (
            <div
              className="text-[14px] leading-relaxed text-[var(--terminal-text)]"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              <span
                className="ml-0.5 inline-block h-4 w-2 animate-pulse bg-[var(--phosphor-green)]"
                data-testid="streaming-cursor"
              />
            </div>
          ) : isStreaming && streamingContent ? (
            <div
              className="text-[14px] leading-relaxed text-[var(--terminal-text)]"
              style={{ fontFamily: 'Inter, system-ui, sans-serif' }}
            >
              <span className="whitespace-pre-wrap">{streamingContent}</span>
              <span
                className="ml-0.5 inline-block h-4 w-2 animate-pulse bg-[var(--phosphor-green)]"
                data-testid="streaming-cursor"
              />
            </div>
          ) : isTyping && !message.content ? (
            <div
              className="flex items-center gap-3 text-sm text-[var(--phosphor-green)]"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              <div className="flex items-center gap-1.5">
                <span
                  className="h-1 w-1 animate-bounce rounded-full bg-[var(--phosphor-green)]"
                  style={{ animationDelay: '0ms' }}
                />
                <span
                  className="h-1 w-1 animate-bounce rounded-full bg-[var(--phosphor-green)]"
                  style={{ animationDelay: '150ms' }}
                />
                <span
                  className="h-1 w-1 animate-bounce rounded-full bg-[var(--phosphor-green)]"
                  style={{ animationDelay: '300ms' }}
                />
              </div>
              <span className="text-[10px] uppercase tracking-wider opacity-70">
                Processing...
              </span>
            </div>
          ) : (
            <div
              className={cn(
                'text-[15px] leading-relaxed',
                isUser
                  ? 'text-[var(--terminal-text)]'
                  : 'text-[var(--terminal-text)]'
              )}
              style={{ fontFamily: 'Inter, system-ui, sans-serif' }}
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

        {!isUser && visibleCitations.length > 0 && (
          <div className="relative border-t border-[var(--terminal-border)] bg-[var(--terminal-bg)]/30 p-3">
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
                  className="group/citation flex items-center gap-2 rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)] px-2.5 py-1.5 text-[10px] transition-all hover:border-[var(--phosphor-green)]/40 hover:bg-[var(--terminal-elevated)]"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  <div className="h-1 w-1 rounded-full bg-[var(--phosphor-green)]/30 transition-colors group-hover/citation:bg-[var(--phosphor-green)]" />
                  <span className="max-w-[180px] truncate text-[var(--terminal-text)]">
                    {citation.title}
                  </span>
                  <span className="border-l border-[var(--terminal-border)] pl-2 text-[var(--terminal-text-dim)]/90">
                    {Math.round(citation.score * 100)}%
                  </span>
                </button>
              ))}
              {message.diagnosticsTraceId && (
                <a
                  href={`/diagnostics?trace=${encodeURIComponent(message.diagnosticsTraceId)}`}
                  className="ml-auto flex items-center gap-1 rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)] px-2 py-1 text-[9px] text-[var(--cyan-pulse)] transition-all hover:border-[var(--cyan-pulse)]/40 hover:bg-[var(--terminal-elevated)]"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
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

export default TerminalChatBubble;
