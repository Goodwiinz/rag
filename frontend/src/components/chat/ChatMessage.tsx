'use client';

import { cn } from '@/lib/utils';
import { Citation } from '@/utils/citationParser';
import { motion } from 'framer-motion';
import { IconButton } from '@/components/ui/icon-button';
import { Check, Copy, FileText, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { CitationRenderer } from './CitationRenderer';

// ============================================
// TYPES
// ============================================

export interface Message {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  citations?: Citation[];
}

export interface ChatMessageProps {
  message: Message;
  index: number;
  modelName?: string;
  isTyping?: boolean;
  isStreaming?: boolean;
  streamingContent?: string;
  onRetry?: () => void;
  onCitationClick?: (citations: Citation[], clickedCitation: Citation) => void;
}

// ============================================
// COMPONENT
// ============================================

export function ChatMessage({
  message,
  index,
  modelName,
  isTyping,
  isStreaming,
  streamingContent,
  onRetry,
  onCitationClick,
}: ChatMessageProps) {
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
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{
        duration: 0.4,
        delay: index * 0.03,
        ease: [0.25, 0.46, 0.45, 0.94],
      }}
      className={cn(
        'group relative mb-6',
        isUser ? 'ml-12 sm:ml-16' : 'mr-12 sm:mr-16'
      )}
    >
      {/* Transmission Line with glow effect */}
      <div
        className={cn(
          'absolute top-0 h-full w-[2px] transition-all duration-300',
          isUser
            ? 'right-0 bg-gradient-to-b from-[var(--amber-gold)] via-[var(--amber-gold)]/50 to-transparent group-hover:shadow-[0_0_8px_var(--amber-gold)]'
            : 'left-0 bg-gradient-to-b from-[var(--phosphor-green)] via-[var(--phosphor-green)]/50 to-transparent group-hover:shadow-[0_0_8px_var(--phosphor-green)]'
        )}
        style={{ opacity: 0.5 }}
      />

      {/* Message Header */}
      <div
        className={cn(
          'flex items-center gap-3 mb-2 text-[10px]',
          isUser ? 'justify-end pr-4' : 'pl-4'
        )}
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        {!isUser && (
          <>
            <div className="flex items-center gap-2">
              <div
                className={cn(
                  'w-1.5 h-1.5 rounded-full bg-[var(--phosphor-green)]',
                  isTyping || isStreaming ? 'animate-pulse' : 'signal-active'
                )}
              />
              <span className="text-[var(--phosphor-green)] uppercase tracking-wider">
                {isTyping || isStreaming ? 'STREAMING' : 'RESPONSE'}
              </span>
            </div>
            {modelName && (
              <span className="text-[var(--terminal-text-muted)]">
                [{modelName}]
              </span>
            )}
          </>
        )}
        {isUser && (
          <span className="text-[var(--amber-gold)] uppercase tracking-wider">
            QUERY
          </span>
        )}
        <span className="text-[var(--terminal-text-muted)]">{timestamp}</span>

        {/* Quick Actions - visible on hover */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
          <IconButton
            icon={copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
            label={copied ? 'Copied!' : 'Copy message'}
            onClick={handleCopy}
            size="sm"
            variant="ghost"
            className={cn(
              'h-6 w-6 p-1 rounded hover:bg-[var(--terminal-elevated)] transition-all [&_svg]:size-3',
              copied
                ? 'text-[var(--phosphor-green)] hover:text-[var(--phosphor-green)] hover:bg-transparent'
                : 'text-[var(--terminal-text-muted)] hover:text-[var(--terminal-text)]'
            )}
          />
          {isUser && onRetry && (
            <IconButton
              icon={<RefreshCw className="w-3 h-3" />}
              label="Retry"
              onClick={onRetry}
              size="sm"
              variant="ghost"
              className="h-6 w-6 p-1 rounded hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-muted)] hover:text-[var(--terminal-text)] transition-all [&_svg]:size-3"
            />
          )}
        </div>
      </div>

      {/* Message Content */}
      <div
        className={cn(
          'relative rounded-lg overflow-hidden',
          isUser
            ? 'bg-gradient-to-br from-[#1a1510] to-[var(--terminal-bg)] border border-[#3d2f1a] mr-4'
            : 'bg-[var(--terminal-surface)] border border-[var(--terminal-border)] ml-4'
        )}
      >
        <div className="absolute inset-0 holo-shimmer opacity-30" />

        <div className="relative p-4">
          {isStreaming && !streamingContent ? (
            /* Streaming: waiting for first token - show pulsing cursor */
            <div
              className="text-sm leading-relaxed text-[var(--terminal-text)]"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              <span className="inline-block w-2 h-4 bg-[#00ff9f] animate-pulse ml-0.5" />
            </div>
          ) : isStreaming && streamingContent ? (
            /* Streaming: rendering incoming tokens with cursor */
            <div
              className="text-sm leading-relaxed text-[var(--terminal-text)]"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              <span className="whitespace-pre-wrap">{streamingContent}</span>
              <span className="inline-block w-2 h-4 bg-[#00ff9f] animate-pulse ml-0.5" />
            </div>
          ) : isTyping && !message.content ? (
            <div
              className="flex items-center gap-3 text-[var(--phosphor-green)] text-sm"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              <div className="flex items-center gap-1">
                <span
                  className="w-2 h-2 rounded-full bg-[var(--phosphor-green)] animate-bounce"
                  style={{ animationDelay: '0ms' }}
                />
                <span
                  className="w-2 h-2 rounded-full bg-[var(--phosphor-green)] animate-bounce"
                  style={{ animationDelay: '150ms' }}
                />
                <span
                  className="w-2 h-2 rounded-full bg-[var(--phosphor-green)] animate-bounce"
                  style={{ animationDelay: '300ms' }}
                />
              </div>
              <span className="opacity-70">Generating response...</span>
            </div>
          ) : (
            <div
              className={cn(
                'text-sm leading-relaxed',
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
                      onCitationClick(
                        message.citations as Citation[],
                        citation
                      );
                    }
                  }}
                />
              )}
            </div>
          )}
        </div>

        {/* Citations */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="border-t border-[var(--terminal-border)] p-3 bg-[var(--terminal-bg)]">
            <div
              className="text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-wider mb-2"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              SOURCES ({message.citations.length})
            </div>
            <div className="flex flex-wrap gap-2">
              {message.citations.map((citation, idx) => (
                <button
                  key={idx}
                  className="flex items-center gap-2 px-2 py-1.5 rounded bg-[var(--terminal-surface)] border border-[var(--terminal-border)] hover:border-[var(--phosphor-green)]/30 text-[10px] transition-colors"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  <FileText className="w-3 h-3 text-[var(--phosphor-green)]" />
                  <span className="text-[var(--terminal-text)] truncate max-w-[150px]">
                    {citation.title}
                  </span>
                  <span className="text-[var(--phosphor-green)]">
                    {Math.round(citation.score * 100)}%
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}

export default ChatMessage;
