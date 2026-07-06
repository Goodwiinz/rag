'use client';

import React, {
  memo,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { VariableSizeList as List } from 'react-window';
import { motion } from 'framer-motion';
import { InlineAgentSummary } from '@/components/chat/shared/InlineAgentSummary';
import { ChatBubble } from '@/components/chat/shared/ChatBubble';
import { AuiMessageByIndex } from '@/components/chat/aui/AuiMessage';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import type { Citation } from '@/utils/citationParser';

const OVERSCAN_COUNT = 5;
const DEFAULT_ROW_HEIGHT = 120;
const MEASURE_PADDING = 8;

/**
 * Total pixel height of the first `addedCount` rows — the amount to shift the
 * scroll offset by on a prepend so the visible messages stay anchored.
 * Extracted so the delta math is unit-testable without react-window in jsdom.
 */
export function prependScrollDelta(
  addedCount: number,
  getItemSize: (index: number) => number
): number {
  let delta = 0;
  for (let i = 0; i < addedCount; i++) delta += getItemSize(i);
  return delta;
}

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
  // Keyed by stable message id so cached heights survive prepend (older-message
  // pagination shifts every index, which would otherwise stale the cache). The
  // index is still passed through for react-window's resetAfterIndex.
  setRowHeight: (messageId: string, height: number, index: number) => void;
}

interface RowProps {
  index: number;
  style: React.CSSProperties;
  data: RowData;
}

const MessageRow = memo(function MessageRow({ index, style, data }: RowProps) {
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
    // Measure the INNER content node (children[0]), not the outer wrapper:
    // react-window imposes the virtual row height on the outer element via
    // `style`, so measuring the outer node feeds the stale imposed height back
    // into the cache. The inner node carries the natural content height.
    const inner = rowRef.current?.children[0] as HTMLElement | undefined;
    if (inner) {
      const height = inner.getBoundingClientRect().height + MEASURE_PADDING;
      setRowHeight(message.id ?? `row-${index}`, height, index);
    }
  }, [
    index,
    message.id,
    setRowHeight,
    message.content,
    isLast,
    storeIsStreaming,
  ]);

  const bubble = (
    <>
      {message.role === 'assistant' && isLast && !storeIsStreaming && (
        <InlineAgentSummary threadId={activeThreadId} />
      )}
      {isLast &&
      isLoading &&
      !storeIsStreaming &&
      message.role === 'assistant' ? (
        <ChatBubble
          message={message}
          index={index}
          modelName="NOUS"
          isTyping
          onRetry={() => onRegenerate(index)}
          onCitationClick={onCitationClick}
          thinkingLabel={thinkingLabel}
        />
      ) : (
        <AuiMessageByIndex
          index={index}
          message={message}
          onRetry={
            message.role === 'assistant' ? () => onRegenerate(index) : undefined
          }
          onCitationClick={onCitationClick}
        />
      )}
    </>
  );

  // rowRef sits on the OUTER (style-bearing) node in both branches; the
  // measured content is always children[0] so getBoundingClientRect reads the
  // natural content height rather than react-window's imposed row height.
  if (shouldAnimate) {
    return (
      <div style={style} ref={rowRef}>
        <motion.div
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
      <div>{bubble}</div>
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
  // Keyed by stable message id (not index): prepending older messages shifts
  // every index, so an index-keyed cache would mis-map heights after pagination.
  const rowHeights = useRef<Record<string, number>>({});
  const [containerHeight, setContainerHeight] = useState(600);
  const containerRef = useRef<HTMLDivElement>(null);
  const prevMessageCountRef = useRef(messages.length);
  const prevLastIdRef = useRef<string | undefined>(
    messages[messages.length - 1]?.id
  );
  const loadOlderTriggeredRef = useRef(false);

  const currentLastId = messages[messages.length - 1]?.id;
  // "New" means a message was APPENDED at the tail (length grew AND the tail id
  // changed). A prepended older batch also grows the length but keeps the same
  // tail id, so it is correctly treated as NOT new — this is what stops the
  // auto-scroll effect from snapping to the bottom on pagination.
  const isNewMessage =
    messages.length > prevMessageCountRef.current &&
    currentLastId !== prevLastIdRef.current;
  useEffect(() => {
    prevMessageCountRef.current = messages.length;
    prevLastIdRef.current = currentLastId;
  }, [messages.length, currentLastId]);

  const lastIndex = messages.length - 1;
  const thinkingLabel = isRetrievingRag ? 'Reading sources' : 'Reflecting';

  // Scroll-to-top detection for loading older messages
  const lastScrollOffsetRef = useRef(0);
  const handleScroll = useCallback(
    ({ scrollOffset }: { scrollOffset: number }) => {
      lastScrollOffsetRef.current = scrollOffset;
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

  const setRowHeight = useCallback(
    (messageId: string, height: number, index: number) => {
      if (rowHeights.current[messageId] !== height) {
        rowHeights.current[messageId] = height;
        listRef.current?.resetAfterIndex(index);
      }
    },
    []
  );

  const getItemSize = useCallback(
    (index: number) =>
      rowHeights.current[messages[index]?.id ?? `row-${index}`] ??
      DEFAULT_ROW_HEIGHT,
    [messages]
  );

  const prevFirstIdRef = useRef<string | undefined>(messages[0]?.id);
  // On prepend the indices shift by the added count: react-window's cached
  // offsets are stale (heights are id-keyed and survive, but offsets are
  // positional) and the current pixel offset now points at different rows.
  // Reset the offset cache and shift the scroll position by the estimated
  // height of the new rows so the visible messages stay anchored.
  // ponytail: unmeasured new rows use DEFAULT_ROW_HEIGHT, so the anchor can
  // be off by (actual - 120)px per row until measurement lands; store real
  // heights from the API response if this is ever noticeable.
  useLayoutEffect(() => {
    const firstId = messages[0]?.id;
    const prevCount = prevMessageCountRef.current;
    const isPrepend =
      messages.length > prevCount &&
      currentLastId === prevLastIdRef.current &&
      firstId !== prevFirstIdRef.current;
    if (isPrepend && listRef.current) {
      const added = messages.length - prevCount;
      listRef.current.resetAfterIndex(0);
      const delta = prependScrollDelta(added, getItemSize);
      listRef.current.scrollTo(lastScrollOffsetRef.current + delta);
    }
    prevFirstIdRef.current = firstId;
  }, [messages, currentLastId, getItemSize]);

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      const height = entries[0]?.contentRect.height;
      if (height && height > 0) setContainerHeight(height);
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Auto-scroll to the newest row ONLY when a message was appended. On a
  // prepended older batch the count also grows, but isNewMessage stays false
  // (prepend is detected separately below), so we keep the user's scroll anchor
  // instead of snapping to the bottom.
  useEffect(() => {
    if (isNewMessage && listRef.current && messages.length > 0) {
      listRef.current.scrollToItem(messages.length - 1, 'end');
    }
  }, [messages.length, isNewMessage]);

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
            className="text-xs font-medium text-(--nous-fg-2) hover:text-(--nous-sol) transition-colors"
          >
            Load older messages
          </button>
        </div>
      )}
      {isLoadingOlder && (
        <div className="flex justify-center py-2">
          <span className="text-xs font-medium text-(--nous-fg-2)">
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
