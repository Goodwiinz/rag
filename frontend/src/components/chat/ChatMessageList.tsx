'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowDown } from 'lucide-react';
import { InlineAgentSummary } from '@/components/chat/shared/InlineAgentSummary';
import { TerminalChatBubble } from '@/components/chat/shared/TerminalChatBubble';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import type { Citation } from '@/utils/citationParser';

export interface ChatMessageListProps {
  messages: ChatPageMessage[];
  activeThreadId: string | null;
  isLoading: boolean;
  storeIsStreaming: boolean;
  storeStreamingContent: string;
  streamingTimestamp: number;
  onRegenerate: (index: number) => void;
  onCitationClick: (citations: Citation[], clickedCitation: Citation) => void;
}

export const ChatMessageList = React.memo(function ChatMessageList({
  messages,
  activeThreadId,
  isLoading,
  storeIsStreaming,
  storeStreamingContent,
  streamingTimestamp,
  onRegenerate,
  onCitationClick,
}: ChatMessageListProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);

  // Auto-scroll when new messages arrive or streaming content updates
  useEffect(() => {
    if (!showScrollButton) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, storeStreamingContent, showScrollButton]);

  // Handle scroll to detect if user scrolled up
  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const { scrollTop, scrollHeight, clientHeight } = container;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
    setShowScrollButton(!isNearBottom && messages.length > 0);
  }, [messages.length]);

  // Scroll to bottom function
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    setShowScrollButton(false);
  }, []);

  return (
    <div className="flex-1 relative min-h-0">
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="h-full overflow-y-auto overflow-x-hidden terminal-scrollbar"
      >
        <div className="max-w-4xl mx-auto pt-3 sm:pt-4 px-2 sm:px-4 pb-4 sm:pb-6">
          <AnimatePresence>
            {messages.map((message, index) => (
              <motion.div
                key={message.id || `msg-${index}`}
                initial={{ opacity: 0, y: 20, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, transition: { duration: 0.2 } }}
                transition={{
                  duration: 0.4,
                  ease: [0.25, 0.46, 0.45, 0.94],
                }}
              >
                {/* Cowork-style inline tool summary: only above the last
                    assistant message, and only when not currently
                    streaming (the streaming bubble shows its own). */}
                {message.role === 'assistant' &&
                  index === messages.length - 1 &&
                  !storeIsStreaming && (
                    <InlineAgentSummary threadId={activeThreadId} />
                  )}
                <TerminalChatBubble
                  message={message}
                  index={index}
                  modelName={
                    message.role === 'assistant' ? 'NOUS AGENT' : undefined
                  }
                  isTyping={
                    index === messages.length - 1 &&
                    isLoading &&
                    !storeIsStreaming &&
                    message.role === 'assistant'
                  }
                  onRetry={
                    message.role === 'assistant'
                      ? () => onRegenerate(index)
                      : undefined
                  }
                  onCitationClick={onCitationClick}
                />
              </motion.div>
            ))}

            {/* Virtual streaming assistant message (shown during SSE streaming) */}
            {storeIsStreaming && (
              <motion.div
                key="streaming-message"
                initial={{ opacity: 0, y: 20, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{
                  opacity: 0,
                  y: -10,
                  transition: { duration: 0.2 },
                }}
                transition={{ duration: 0.3 }}
              >
                <InlineAgentSummary threadId={activeThreadId} />
                <TerminalChatBubble
                  message={{
                    role: 'assistant',
                    content: '',
                    timestamp: streamingTimestamp,
                  }}
                  index={messages.length}
                  modelName="NOUS AGENT"
                  isStreaming={true}
                  streamingContent={storeStreamingContent}
                  onCitationClick={onCitationClick}
                />
              </motion.div>
            )}
          </AnimatePresence>
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Scroll to bottom button - Absolute positioned within wrapper */}
      <AnimatePresence>
        {showScrollButton && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-50 pointer-events-none">
            <motion.button
              initial={{ opacity: 0, y: 10, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.9 }}
              onClick={scrollToBottom}
              className="flex items-center gap-2 px-4 py-2 rounded-full bg-[var(--phosphor-green)] text-[var(--terminal-bg)] text-xs font-bold shadow-[0_0_20px_var(--phosphor-green-glow)] hover:shadow-[0_0_30px_var(--phosphor-green-glow)] transition-all pointer-events-auto border border-[var(--terminal-bg)]"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              <ArrowDown className="w-4 h-4" />
              <span className="hidden sm:inline tracking-wider">
                NEW MESSAGES
              </span>
            </motion.button>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
});
