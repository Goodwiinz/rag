'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowDown } from 'lucide-react';
import { InlineAgentSummary } from '@/components/chat/shared/InlineAgentSummary';
import { ChatBubble } from '@/components/chat/shared/ChatBubble';
import { VirtualizedMessageList } from '@/components/chat/VirtualizedMessageList';
import { CommandOutputBubble } from '@/components/chat/CommandOutputBubble';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import type {
  CommandAction,
  CommandOutput,
} from '@/components/chat/commandOutput';
import type { Citation } from '@/utils/citationParser';
import { useChatStore } from '@/store/chat-store';

const MESSAGE_VIRTUALIZATION_THRESHOLD = 75;

export interface ChatMessageListProps {
  messages: ChatPageMessage[];
  activeThreadId: string | null;
  isLoading: boolean;
  storeIsStreaming: boolean;
  storeStreamingContent: string;
  streamingTimestamp: number;
  onRegenerate: (index: number) => void;
  onCitationClick: (
    citations: Citation[],
    clickedCitation: Citation,
    traceId?: string
  ) => void;
  /** Ephemeral CLI command output, rendered at the bottom of the transcript. */
  commandOutputs?: CommandOutput[];
  onCommandItemAction?: (action: CommandAction) => void;
  /** True while RAG retrieval is in flight (drives the thinking-pill label). */
  isRetrievingRag?: boolean;
  /** Pagination: load older messages. */
  onLoadOlder?: () => void;
  /** Pagination: more messages available on the server. */
  hasMore?: boolean;
  /** Pagination: currently fetching older messages. */
  isLoadingOlder?: boolean;
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
  commandOutputs,
  onCommandItemAction,
  isRetrievingRag,
  onLoadOlder,
  hasMore,
  isLoadingOlder,
}: ChatMessageListProps) {
  // Live citations captured mid-stream (set once by onRagContext); used to
  // surface a subtle "reading sources" chip while the answer streams.
  const streamingCitations = useChatStore((s) => s.streamingCitations);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const scrollRafRef = useRef<number | null>(null);
  const prevMessageCountRef = useRef(messages.length);

  // Throttled auto-scroll: only one scrollIntoView per animation frame.
  // Depends on message count + streaming state, NOT on storeStreamingContent
  // (which changes every rAF frame during streaming). The streaming bubble
  // is rendered separately and grows the scroll height naturally; this
  // effect just needs to keep the view pinned to the bottom.
  useEffect(() => {
    if (showScrollButton) return;
    if (scrollRafRef.current !== null) return;
    scrollRafRef.current = requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      scrollRafRef.current = null;
    });
  }, [messages.length, storeIsStreaming, commandOutputs, showScrollButton]);

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
  const loadOlderTriggeredRef = useRef(false);
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

      // Auto-trigger load older when scrolled near the top
      if (
        onLoadOlder &&
        hasMore &&
        !isLoadingOlder &&
        !loadOlderTriggeredRef.current &&
        scrollTop < 150 &&
        messages.length > 0
      ) {
        loadOlderTriggeredRef.current = true;
        onLoadOlder();
      }
      // Reset the trigger guard when scrolling back down
      if (scrollTop > 300) {
        loadOlderTriggeredRef.current = false;
      }
    });
  }, [messages.length, onLoadOlder, hasMore, isLoadingOlder]);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    setShowScrollButton(false);
  }, []);

  const lastIndex = messages.length - 1;
  // Phase-aware "thinking" label (the pill only shows before any token arrives).
  const thinkingLabel = isRetrievingRag ? 'Reading sources' : 'Reflecting';

  // Memoize the committed message list so it doesn't re-map on every
  // streaming token. The streaming bubble (below) reads storeStreamingContent
  // and streamingCitations directly and is outside this memo. Dependencies
  // are only things that actually change the committed list's output.
  const renderedMessages = useMemo(
    () =>
      messages.map((message, index) => {
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
              modelName={message.role === 'assistant' ? 'NOUS' : undefined}
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
              thinkingLabel={thinkingLabel}
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

        return <div key={message.id || `msg-${index}`}>{bubble}</div>;
      }),
    [
      messages,
      lastIndex,
      isNewMessage,
      storeIsStreaming,
      activeThreadId,
      isLoading,
      onRegenerate,
      onCitationClick,
      thinkingLabel,
    ]
  );

  return (
    <div className="flex-1 relative min-h-0">
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="h-full overflow-y-auto overflow-x-hidden nous-scrollbar"
      >
        <div className="max-w-[var(--nous-chat-col)] mx-auto pt-3 sm:pt-4 px-2 sm:px-4 pb-4 sm:pb-6">
          {/* Load older messages indicator */}
          {hasMore && !isLoadingOlder && messages.length > 0 && (
            <div className="flex justify-center py-2">
              <button
                onClick={onLoadOlder}
                className="text-xs font-medium text-[var(--nous-fg-2)] hover:text-[var(--nous-sol)] transition-colors"
              >
                Load older messages
              </button>
            </div>
          )}
          {isLoadingOlder && (
            <div className="flex justify-center py-2">
              <span
                className="text-xs font-medium text-[var(--nous-fg-2)]"
              >
                Loading older messages...
              </span>
            </div>
          )}

          {messages.length > MESSAGE_VIRTUALIZATION_THRESHOLD ? (
            <VirtualizedMessageList
              messages={messages}
              activeThreadId={activeThreadId}
              isLoading={isLoading}
              storeIsStreaming={storeIsStreaming}
              onRegenerate={onRegenerate}
              onCitationClick={onCitationClick}
              isRetrievingRag={isRetrievingRag}
              onLoadOlder={onLoadOlder}
              hasMore={hasMore}
              isLoadingOlder={isLoadingOlder}
            />
          ) : (
            renderedMessages
          )}

          {/* Streaming assistant message.
              Hide it the instant the streamed answer is COMMITTED — i.e. the
              last message is an assistant turn whose content equals what we
              streamed. Both derive from the same React list, so the bubble
              unmounts in the same render the final message appears. Gating only
              on the Zustand `storeIsStreaming` flag raced the React message
              append across two reactive systems, leaving a window where the
              same answer painted twice (streamed bubble + committed bubble).
              We compare CONTENT, not just role: during a regenerate the stale
              assistant answer is still the last message while a NEW stream is
              in flight, so a role-only check would wrongly hide the live bubble
              for the whole turn. The exit is instant so the exiting bubble
              can't repaint the full streamed answer over the committed one. */}
          <AnimatePresence>
            {storeIsStreaming &&
              !(
                messages[messages.length - 1]?.role === 'assistant' &&
                messages[messages.length - 1]?.content === storeStreamingContent
              ) && (
                <motion.div
                  key="streaming-message"
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, transition: { duration: 0 } }}
                  transition={{ duration: 0.25 }}
                >
                  <InlineAgentSummary threadId={activeThreadId} />
                  {streamingCitations.length > 0 && (
                    <div
                      role="status"
                      aria-live="polite"
                      className="mb-1.5 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-nous-mono text-[10px]"
                      style={{
                        color: 'var(--nous-fg-2)',
                        backgroundColor: 'var(--nous-bg-2)',
                        borderColor: 'var(--nous-border-1)',
                      }}
                    >
                      <span
                        className="h-1.5 w-1.5 shrink-0 rounded-full"
                        style={{ backgroundColor: 'var(--nous-sol)' }}
                      />
                      Reading {streamingCitations.length}{' '}
                      {streamingCitations.length === 1 ? 'source' : 'sources'}
                    </div>
                  )}
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
                    thinkingLabel={thinkingLabel}
                  />
                </motion.div>
              )}
          </AnimatePresence>

          {/* Ephemeral CLI command output (not persisted, not sent to agent) */}
          {commandOutputs?.map((output) => (
            <CommandOutputBubble
              key={output.id}
              output={output}
              onItemAction={(action) => onCommandItemAction?.(action)}
            />
          ))}
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
              <span className="hidden sm:inline">New messages</span>
            </motion.button>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
});
