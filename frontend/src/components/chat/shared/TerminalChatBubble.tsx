'use client';

import { cn } from '@/lib/utils';
import type { Citation } from '@/utils/citationParser';
import { Check, Copy, RefreshCw } from 'lucide-react';
import { useState } from 'react';
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
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={cn(
        'group relative mb-4',
        isUser ? 'ml-8 sm:ml-16' : 'mr-8 sm:mr-16'
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
          'mb-1.5 flex items-center gap-3 text-[10px] tracking-wider',
          isUser ? 'justify-end pr-4' : 'pl-4'
        )}
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        {!isUser && (
          <>
            <div className="rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)] px-1.5 py-0.5">
              <span className="text-[9px] font-bold text-[var(--phosphor-green)]">
                {isTyping || isStreaming ? 'STREAMING' : 'RECEIVED'}
              </span>
            </div>
            {modelName && (
              <span className="rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)] px-1.5 py-0.5 text-[var(--terminal-text-dim)]">
                {modelName}
              </span>
            )}
          </>
        )}
        {isUser && (
          <span className="rounded border border-[var(--amber-gold)]/20 bg-[var(--amber-gold)]/10 px-1.5 py-0.5 text-[9px] font-bold text-[var(--amber-gold)]">
            QUERY
          </span>
        )}
        <span className="text-[var(--terminal-text-dim)]">{timestamp}</span>

        <div className="flex items-center gap-1 opacity-0 transition-all duration-200 group-hover:opacity-100">
          <button
            onClick={handleCopy}
            className={cn(
              'rounded border border-transparent p-1 transition-all hover:border-[var(--terminal-border)] hover:bg-[var(--terminal-elevated)]',
              copied
                ? 'text-[var(--phosphor-green)]'
                : 'text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)]'
            )}
            title={copied ? 'Copied!' : 'Copy message'}
          >
            {copied ? (
              <Check className="h-3.5 w-3.5" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
          </button>
          {isUser && onRetry && (
            <button
              onClick={onRetry}
              className="rounded border border-transparent p-1 text-[var(--terminal-text-dim)] transition-all hover:border-[var(--terminal-border)] hover:bg-[var(--terminal-elevated)] hover:text-[var(--terminal-text)]"
              title="Retry"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      <div
        className={cn(
          'relative overflow-hidden rounded-xl border shadow-sm backdrop-blur-sm transition-all duration-300',
          isUser
            ? 'mr-4 border-[var(--amber-gold)]/20 bg-gradient-to-br from-[var(--terminal-elevated)] to-[var(--terminal-bg)] hover:border-[var(--amber-gold)]/40'
            : 'ml-4 border-[var(--terminal-border)] bg-[var(--terminal-surface)] hover:border-[var(--phosphor-green)]/30'
        )}
      >
        <div className="pointer-events-none absolute inset-0 z-0 bg-[linear-gradient(rgba(18,18,18,0)_50%,rgba(0,0,0,0.2)_50%)] bg-[length:100%_2px] opacity-10" />

        <div className="relative z-10 p-4 sm:p-5">
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
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              <span className="whitespace-pre-wrap">{streamingContent}</span>
              <span
                className="ml-0.5 inline-block h-4 w-2 animate-pulse bg-[var(--phosphor-green)]"
                data-testid="streaming-cursor"
              />
            </div>
          ) : (
            <div
              className={cn(
                'text-[14px] leading-relaxed',
                isUser ? 'text-[#e8d5b5]' : 'text-[var(--terminal-text)]'
              )}
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              {isUser ? (
                <p className="whitespace-pre-wrap">{message.content}</p>
              ) : (
                <CitationRenderer
                  content={message.content}
                  citations={message.citations as Citation[]}
                  onCitationClick={(citation) => {
                    if (onCitationClick && message.citations) {
                      onCitationClick(message.citations as Citation[], citation);
                    }
                  }}
                />
              )}
            </div>
          )}
        </div>

        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="relative border-t border-[var(--terminal-border)] bg-[var(--terminal-bg)]/30 p-2.5">
            <div className="flex flex-wrap items-center gap-1.5">
              {message.citations.map((citation, idx) => (
                <button
                  key={idx}
                  className="group/citation flex items-center gap-1.5 rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)] px-2 py-1 text-[9px] transition-all hover:border-[var(--phosphor-green)]/40 hover:bg-[var(--terminal-elevated)]"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  <div className="h-1 w-1 rounded-full bg-[var(--phosphor-green)]/30 transition-colors group-hover/citation:bg-[var(--phosphor-green)]" />
                  <span className="max-w-[150px] truncate text-[var(--terminal-text)]">
                    {citation.title}
                  </span>
                  <span className="border-l border-[var(--terminal-border)] pl-1.5 text-[var(--terminal-text-dim)]">
                    {Math.round(citation.score * 100)}%
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default TerminalChatBubble;

