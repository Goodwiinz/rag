'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowDown } from 'lucide-react';
import { InlineAgentSummary } from '@/components/chat/shared/InlineAgentSummary';
import { ChatBubble } from '@/components/chat/shared/ChatBubble';
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
  const scrollRafRef = useRef<number | null>(null);
  const prevMessageCountRef = useRef(messages.length);

  // Throttled auto-scroll: only one scrollIntoView per animation frame
  useEffect(() => {
    if (showScrollButton) return;
    if (scrollRafRef.current !== null) return;
    scrollRafRef.current = requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      scrollRafRef.current = null;
    });
  }, [messages, storeStreamingContent, showScrollButton]);

  useEffect(() => {
    return () => {
      if (scrollRafRef.current !== null) {
        cancelAnimationFrame(scrollRafRef.current);
      }
    };
  }, []);

  // Track which messages are "new" for entrance animation
  const isNewMessage = messages.length > prevMessageCountRef.current;
  useEffect(() => {
    prevMessageCountRef.current = messages.length;
  }, [messages.length]);

  const scrollTickRef = useRef(false);
  const handleScroll = useCallback(() => {
    if (scrollTickRef.current) return;
    scrollTickRef.current = true;
    requestAnimationFrame(() => {
      scrollTickRef.current = false;
      const container = scrollContainerRef.current;
      if (!container) return;
      const { scrollTop, scrollHeight, clientHeight } = container;
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
      setShowScrollButton(!isNearBottom && messages.length > 0);
    });
  }, [messages.length]);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    setShowScrollButton(false);
  }, []);

  const lastIndex = messages.length - 1;

  return (
    <div className="flex-1 relative min-h-0">
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="h-full overflow-y-auto overflow-x-hidden nous-scrollbar"
      >
        <div className="max-w-4xl mx-auto pt-3 sm:pt-4 px-2 sm:px-4 pb-4 sm:pb-6">
          {messages.map((message, index) => {
            const isLast = index === lastIndex;
            const shouldAnimate = isLast && isNewMessage;

            const bubble = (
              <>
                {message.role === 'assistant' &&
                  isLast &&
                  !storeIsStreaming && (
                    <InlineAgentSummary threadId={activeThreadId} />
                  )}
                <ChatBubble
                  message={message}
                  index={index}
                  modelName={
                    message.role === 'assistant' ? 'NOUS' : undefined
                  }
                  isTyping={
                    isLast &&
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
              </>
            );

            if (shouldAnimate) {
              return (
                <motion.div
                  key={message.id || `msg-${index}`}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{
                    duration: 0.3,
                    ease: [0.25, 0.46, 0.45, 0.94],
                  }}
                >
                  {bubble}
                </motion.div>
              );
            }

            return (
              <div key={message.id || `msg-${index}`}>
                {bubble}
              </div>
            );
          })}

          {/* Streaming assistant message */}
          <AnimatePresence>
            {storeIsStreaming && (
              <motion.div
                key="streaming-message"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, transition: { duration: 0.15 } }}
                transition={{ duration: 0.25 }}
              >
                <InlineAgentSummary threadId={activeThreadId} />
                <ChatBubble
                  message={{
                    role: 'assistant',
                    content: '',
                    timestamp: streamingTimestamp,
                  }}
                  index={messages.length}
                  modelName="NOUS"
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

      {/* Scroll to bottom button */}
      <AnimatePresence>
        {showScrollButton && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-50 pointer-events-none">
            <motion.button
              initial={{ opacity: 0, y: 10, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.9 }}
              onClick={scrollToBottom}
              className="flex items-center justify-center w-9 h-9 sm:w-auto sm:h-auto sm:gap-2 sm:px-4 sm:py-2 rounded-full bg-[var(--nous-sol)] text-[var(--nous-erebus)] text-xs font-semibold shadow-md hover:shadow-lg transition-all pointer-events-auto"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              <ArrowDown className="w-4 h-4" />
              <span className="hidden sm:inline">
                New messages
              </span>
            </motion.button>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
});
