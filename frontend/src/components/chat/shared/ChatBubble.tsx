'use client';

import { cn } from '@/lib/utils';
import { getReferencedCitations, type Citation } from '@/utils/citationParser';
import {
  Activity,
  Check,
  Clock,
  Copy,
  RefreshCw,
  Search,
  Sparkles,
  Square,
} from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import React, { useMemo, useState } from 'react';
import { CitationRenderer } from '../CitationRenderer';

export interface ChatBubbleMessage {
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
    stopped?: boolean;
  };
}

export interface ChatBubbleProps {
  message: ChatBubbleMessage;
  index: number;
  modelName?: string;
  isTyping?: boolean;
  isStreaming?: boolean;
  streamingContent?: string;
  onRetry?: () => void;
  onCitationClick?: (
    citations: Citation[],
    clickedCitation: Citation,
    traceId?: string
  ) => void;
  /** Label for the pre-token "thinking" pill (phase-aware). */
  thinkingLabel?: string;
}

function ToolStrip({
  toolsUsed,
  sourcesCount,
  responseTimeMs,
  stopped,
}: {
  toolsUsed?: string[];
  sourcesCount?: number;
  responseTimeMs?: number;
  stopped?: boolean;
}) {
  const hasAny =
    (toolsUsed && toolsUsed.length > 0) ||
    (sourcesCount && sourcesCount > 0) ||
    (responseTimeMs && responseTimeMs > 0) ||
    stopped;
  if (!hasAny) return null;

  // Only claim "Searched" when the agent actually retrieved/used tools; a
  // response can carry just a timing with no sources (e.g. RAG off).
  const didSearch =
    (toolsUsed && toolsUsed.length > 0) || (sourcesCount && sourcesCount > 0);

  return (
    <div className="nous-tool-strip">
      {didSearch && (
        <>
          <div className="nous-tool-strip-icon">
            <Search className="w-2.5 h-2.5" strokeWidth={2} />
          </div>
          <span className="nous-tool-strip-label">Searched</span>
          {toolsUsed?.slice(0, 3).map((tool) => (
            <React.Fragment key={tool}>
              <span className="nous-tool-strip-sep" />
              <span className="nous-tool-strip-chip">{tool}</span>
            </React.Fragment>
          ))}
          {sourcesCount && sourcesCount > 0 && (
            <>
              <span className="nous-tool-strip-sep" />
              <span className="nous-tool-strip-chip">
                {sourcesCount} {sourcesCount === 1 ? 'source' : 'sources'}
              </span>
            </>
          )}
        </>
      )}
      {responseTimeMs && responseTimeMs > 0 && (
        <span className="nous-tool-strip-time inline-flex items-center gap-1">
          <Clock className="w-2.5 h-2.5" strokeWidth={2} />
          {(responseTimeMs / 1000).toFixed(1)}s
        </span>
      )}
      {stopped && (
        <span
          className="inline-flex items-center gap-1 text-[10px] font-medium text-[var(--nous-fg-3)]"
          title="You stopped this response; the text above is partial."
        >
          <Square className="w-2 h-2" strokeWidth={2.4} />
          Stopped
        </span>
      )}
    </div>
  );
}

export const ChatBubble = React.memo(function ChatBubble({
  message,
  index: _index,
  modelName,
  isTyping,
  isStreaming,
  streamingContent,
  onRetry,
  onCitationClick,
  thinkingLabel = 'Thinking',
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

  const allCitations = message.citations ?? [];

  const inlineCitations = useMemo(
    () => getReferencedCitations(message.content, allCitations),
    [message.content, allCitations]
  );

  // Show inline-referenced citations when available, otherwise fall back
  // to all attached citations so footer chips + tool strip always render
  // when the backend attached sources — even if the AI didn't use [Doc N].
  const visibleCitations =
    inlineCitations.length > 0 ? inlineCitations : allCitations;

  const stripSourcesCount =
    message.metadata?.sourcesCount ?? visibleCitations.length;
  const stripToolsUsed = message.metadata?.toolsUsed;
  const stripResponseMs = message.metadata?.responseTimeMs;

  return (
    <div className="group relative mb-7 sm:mb-8">
      {/* Content column */}
      <div className={cn('min-w-0', isUser ? 'text-right' : 'text-left')}>
        {/* Meta row — role + model pill + time */}
        <div
          className={cn(
            'mb-2 flex items-center gap-2.5',
            isUser ? 'justify-end' : ''
          )}
        >
          {!isUser && (
            <>
              <span
                className="text-[12px] font-medium text-[var(--nous-fg-3)]"
                style={{ fontFamily: 'var(--nous-font-ui)' }}
              >
                Assistant
              </span>
              {modelName && (
                <span
                  className="inline-flex items-center gap-1 px-2 py-[2px] rounded text-[10px] font-semibold bg-[var(--nous-aurum)] text-[var(--nous-sol-safe)] dark:bg-[var(--nous-ember)] dark:text-[var(--nous-helios)]"
                  style={{ fontFamily: 'var(--nous-font-ui)' }}
                >
                  <Sparkles className="w-2.5 h-2.5" strokeWidth={2} />
                  {modelName}
                </span>
              )}
            </>
          )}
          {isUser && (
            <span
              className="text-[12px] font-medium text-[var(--nous-fg-3)]"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              You
            </span>
          )}
          <span
            className="inline-flex items-center gap-1 text-[11px] text-[var(--nous-fg-3)]"
            style={{ fontFamily: 'var(--nous-font-ui)' }}
          >
            <Clock className="w-2.5 h-2.5" strokeWidth={2} />
            {timestamp}
          </span>
        </div>

        {/* Tool strip — only when we have something to show */}
        {!isUser && !isStreaming && !isTyping && (
          <ToolStrip
            toolsUsed={stripToolsUsed}
            sourcesCount={stripSourcesCount}
            responseTimeMs={stripResponseMs}
            stopped={message.metadata?.stopped}
          />
        )}

        {/* Body
            — user: scholarly pill (nous-bubble-user)
            — assistant: NO wrapper — serif body sits directly on parchment,
              matching the hybrid-chat reference where the assistant column
              reads as a manuscript margin, not a chat card. */}
        {isUser ? (
          <div
            className={cn(
              'nous-bubble-user relative inline-block px-4 py-2.5 text-left',
              'max-w-[92%] sm:max-w-[540px] transition-shadow hover:shadow-md'
            )}
          >
            <div className="nous-chat-body">
              <p className="whitespace-pre-wrap text-[14px] leading-relaxed">
                {message.content}
              </p>
            </div>
          </div>
        ) : (
          <div className="relative">
            {isStreaming && !streamingContent ? (
              <ThinkingPill label={thinkingLabel} />
            ) : isStreaming && streamingContent ? (
              <div className="nous-chat-body">
                <span className="whitespace-pre-wrap">{streamingContent}</span>
                <span
                  className="ml-0.5 inline-block h-4 w-[3px] rounded-sm align-text-bottom animate-pulse bg-[var(--nous-sol)] dark:bg-[var(--nous-helios)]"
                  data-testid="streaming-cursor"
                />
              </div>
            ) : isTyping && !message.content ? (
              <ThinkingPill label={thinkingLabel} />
            ) : (
              <div className="nous-chat-body">
                <CitationRenderer
                  content={message.content}
                  citations={message.citations as Citation[]}
                  onCitationClick={(citation) => {
                    if (onCitationClick) {
                      onCitationClick(
                        visibleCitations,
                        citation,
                        message.diagnosticsTraceId
                      );
                    }
                  }}
                />
              </div>
            )}
          </div>
        )}

        {/* Citations footer chips */}
        {!isUser &&
          visibleCitations.length > 0 &&
          !isStreaming &&
          !isTyping && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {visibleCitations.map((citation, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    if (onCitationClick) {
                      onCitationClick(
                        visibleCitations,
                        citation,
                        message.diagnosticsTraceId
                      );
                    }
                  }}
                  className="group/citation flex items-center gap-2 rounded-md border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] px-2.5 py-1.5 text-[10px] transition-all hover:border-[var(--nous-sol)]/40 hover:bg-[var(--nous-aurum)] dark:hover:bg-[var(--nous-ember)]"
                  style={{ fontFamily: 'var(--nous-font-mono)' }}
                >
                  <div className="h-1.5 w-1.5 rounded-full bg-[var(--nous-sol)]/40 transition-colors group-hover/citation:bg-[var(--nous-sol)] dark:bg-[var(--nous-helios)]/40 dark:group-hover/citation:bg-[var(--nous-helios)]" />
                  <span className="max-w-[180px] truncate text-[var(--nous-fg-1)]">
                    {citation.title}
                  </span>
                  <span className="border-l border-[var(--nous-border-1)] pl-2 text-[var(--nous-fg-3)] tabular-nums">
                    {Math.round(citation.score * 100)}%
                  </span>
                </button>
              ))}
              {message.diagnosticsTraceId && (
                <a
                  href={`/diagnostics?trace=${encodeURIComponent(message.diagnosticsTraceId)}`}
                  className="ml-auto flex items-center gap-1 rounded-md border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] px-2 py-1 text-[9px] text-[var(--nous-fg-3)] transition-all hover:border-[var(--nous-sol)]/40 hover:text-[var(--nous-sol-safe)] dark:hover:text-[var(--nous-helios)]"
                  style={{ fontFamily: 'var(--nous-font-mono)' }}
                  title="View retrieval diagnostics"
                >
                  <Activity className="h-3 w-3" />
                  <span>DIAG</span>
                </a>
              )}
            </div>
          )}

        {/* Scholarly action row — visible on hover */}
        {!isUser && !isStreaming && !isTyping && message.content && (
          <div className="nous-msg-actions">
            <button
              onClick={handleCopy}
              className="nous-msg-action"
              aria-label={copied ? 'Copied!' : 'Copy message'}
              title={copied ? 'Copied!' : 'Copy message'}
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-[var(--nous-terra)]" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </button>
            {onRetry && (
              <button
                onClick={onRetry}
                className="nous-msg-action"
                aria-label="Regenerate response"
                title="Regenerate response"
              >
                <RefreshCw className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        )}

        {/* User message: copy on hover */}
        {isUser && message.content && (
          <div className="nous-msg-actions justify-end">
            <button
              onClick={handleCopy}
              className="nous-msg-action"
              aria-label={copied ? 'Copied!' : 'Copy message'}
              title={copied ? 'Copied!' : 'Copy message'}
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-[var(--nous-terra)]" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
});

function ThinkingPill({ label }: { label: string }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className="nous-streaming-pill"
      role="status"
      aria-live="polite"
      initial={reduce ? false : { opacity: 0, y: 2 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
    >
      <span
        className="w-2 h-2 rounded-full bg-[var(--nous-sol)] dark:bg-[var(--nous-helios)]"
        style={{
          boxShadow: '0 0 0 3px rgba(212, 160, 57, 0.18)',
          animation: 'nous-pulse 1.4s ease-in-out infinite',
        }}
      />
      <span>{label}</span>
    </motion.div>
  );
}

export default ChatBubble;
