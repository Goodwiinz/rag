'use client';

import React, {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { VariableSizeList as List } from 'react-window';
import { AnimatePresence, motion } from 'framer-motion';
import { InlineAgentSummary } from '@/components/chat/shared/InlineAgentSummary';
import { ChatBubble } from '@/components/chat/shared/ChatBubble';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import type {
  CommandAction,
  CommandOutput,
} from '@/components/chat/commandOutput';
import type { Citation } from '@/utils/citationParser';

const VIRTUALIZATION_THRESHOLD = 75;
const OVERSCAN_COUNT = 5;
const DEFAULT_ROW_HEIGHT = 120;
const MEASURE_PADDING = 8;

interface VirtualizedMessageListProps {
  messages: ChatPageMessage[];
  activeThreadId: string | null;
  isLoading: boolean;
  storeIsStreaming: boolean;
  onRegenerate: (index: number) => void;
  onCitationClick: (
    citations: Citation[],
    clickedCitation: Citation,
    traceId?: string
  ) => void;
  isRetrievingRag?: boolean;
  onLoadOlder?: () => void;
  hasMore?: boolean;
  isLoadingOlder?: boolean;
}

interface RowData {
  messages: ChatPageMessage[];
  lastIndex: number;
  isNewMessage: boolean;
  activeThreadId: string | null;
  storeIsStreaming: boolean;
  isLoading: boolean;
  onRegenerate: (index: number) => void;
  onCitationClick: (
    citations: Citation[],
    clickedCitation: Citation,
    traceId?: string
  ) => void;
  thinkingLabel: string;
  setRowHeight: (index: number, height: number) => void;
}

interface RowProps {
  index: number;
  style: React.CSSProperties;
  data: RowData;
}

const MessageRow = memo(function MessageRow({
  index,
  style,
  data,
}: RowProps) {
  const {
    messages,
    lastIndex,
    isNewMessage,
    activeThreadId,
    storeIsStreaming,
    isLoading,
    onRegenerate,
    onCitationClick,
    thinkingLabel,
    setRowHeight,
  } = data;

  const message = messages[index];
  const isLast = index === lastIndex;
  const shouldAnimate = isLast && isNewMessage;
  const rowRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (rowRef.current) {
      const height = rowRef.current.getBoundingClientRect().height + MEASURE_PADDING;
      setRowHeight(index, height);
    }
  }, [index, setRowHeight, message.content, isLast, storeIsStreaming]);

  const bubble = (
    <>
      {message.role === 'assistant' && isLast && !storeIsStreaming && (
        <InlineAgentSummary threadId={activeThreadId} />
      )}
      <ChatBubble
        message={message}
        index={index}
        modelName={message.role === 'assistant' ? 'NOUS' : undefined}
        isTyping={isLast && isLoading && !storeIsStreaming && message.role === 'assistant'}
        onRetry={message.role === 'assistant' ? () => onRegenerate(index) : undefined}
        onCitationClick={onCitationClick}
        thinkingLabel={thinkingLabel}
      />
    </>
  );

  if (shouldAnimate) {
    return (
      <div style={style}>
        <motion.div
          ref={rowRef}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
        >
          {bubble}
        </motion.div>
      </div>
    );
  }

  return (
    <div style={style} ref={rowRef}>
      {bubble}
    </div>
  );
});

export const VirtualizedMessageList = memo(function VirtualizedMessageList({
  messages,
  activeThreadId,
  isLoading,
  storeIsStreaming,
  onRegenerate,
  onCitationClick,
  isRetrievingRag,
  onLoadOlder,
  hasMore,
  isLoadingOlder,
}: VirtualizedMessageListProps) {
  const listRef = useRef<List<RowData>>(null);
  const rowHeights = useRef<Record<number, number>>({});
  const [containerHeight, setContainerHeight] = useState(600);
  const containerRef = useRef<HTMLDivElement>(null);
  const prevMessageCountRef = useRef(messages.length);
  const loadOlderTriggeredRef = useRef(false);

  const isNewMessage = messages.length > prevMessageCountRef.current;
  useEffect(() => {
    prevMessageCountRef.current = messages.length;
  }, [messages.length]);

  const lastIndex = messages.length - 1;
  const thinkingLabel = isRetrievingRag ? 'Reading sources' : 'Reflecting';

  // Scroll-to-top detection for loading older messages
  const handleScroll = useCallback(
    ({ scrollOffset }: { scrollOffset: number }) => {
      if (
        onLoadOlder &&
        hasMore &&
        !isLoadingOlder &&
        !loadOlderTriggeredRef.current &&
        scrollOffset < 50 &&
        messages.length > 0
      ) {
        loadOlderTriggeredRef.current = true;
        onLoadOlder();
      }
      if (scrollOffset > 200) {
        loadOlderTriggeredRef.current = false;
      }
    },
    [onLoadOlder, hasMore, isLoadingOlder, messages.length]
  );

  const setRowHeight = useCallback((index: number, height: number) => {
    if (rowHeights.current[index] !== height) {
      rowHeights.current[index] = height;
      listRef.current?.resetAfterIndex(index);
    }
  }, []);

  const getItemSize = useCallback(
    (index: number) => rowHeights.current[index] ?? DEFAULT_ROW_HEIGHT,
    []
  );

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      const height = entries[0]?.contentRect.height;
      if (height && height > 0) setContainerHeight(height);
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (listRef.current && messages.length > 0) {
      listRef.current.scrollToItem(messages.length - 1, 'end');
    }
  }, [messages.length]);

  const itemData = useMemo<RowData>(
    () => ({
      messages,
      lastIndex,
      isNewMessage,
      activeThreadId,
      storeIsStreaming,
      isLoading,
      onRegenerate,
      onCitationClick,
      thinkingLabel,
      setRowHeight,
    }),
    [
      messages,
      lastIndex,
      isNewMessage,
      activeThreadId,
      storeIsStreaming,
      isLoading,
      onRegenerate,
      onCitationClick,
      thinkingLabel,
      setRowHeight,
    ]
  );

  return (
    <div ref={containerRef} className="h-full">
      {/* Load older indicator at the top */}
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
          <span className="text-xs font-medium text-[var(--nous-fg-2)]">
            Loading older messages...
          </span>
        </div>
      )}
      <List
        ref={listRef}
        height={containerHeight}
        width="100%"
        itemCount={messages.length}
        itemSize={getItemSize}
        itemData={itemData}
        overscanCount={OVERSCAN_COUNT}
        onScroll={handleScroll}
        className="nous-scrollbar"
      >
        {MessageRow}
      </List>
    </div>
  );
});
