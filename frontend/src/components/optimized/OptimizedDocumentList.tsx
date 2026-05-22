/**
 * High-performance document list component with virtual scrolling,
 * lazy loading, and real-time status updates
 * Optimized for handling thousands of documents with sub-100ms response times
 */

import React, {
  useState,
  useEffect,
  useCallback,
  useMemo,
  useRef,
  memo,
  lazy,
  Suspense,
} from 'react';
import { FixedSizeList as List } from 'react-window';
import { Waypoint } from 'react-waypoint';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { debounce, throttle } from 'lodash-es';
import { Document, ProcessingStatus } from '@/types/api';
import { useWebSocketConnection } from '@/hooks/useWebSocketConnection';
import { performanceMonitor } from '@/utils/performance';
import { api } from '@/services/api-client';

// Lazy load heavy components
const DocumentRow = lazy(() => import('./DocumentRow'));
const DocumentSkeleton = lazy(() => import('./DocumentSkeleton'));

// Performance constants
const ITEM_HEIGHT = 80; // pixels
const BUFFER_SIZE = 5; // Number of items to render outside viewport
const BATCH_SIZE = 20; // Items to fetch per batch
const DEBOUNCE_DELAY = 300; // milliseconds
const THROTTLE_DELAY = 100; // milliseconds

interface OptimizedDocumentListProps {
  organizationId: string;
  filters?: {
    status?: ProcessingStatus;
    search?: string;
    dateRange?: {
      start: Date;
      end: Date;
    };
  };
  onDocumentSelect?: (document: Document) => void;
  onDocumentStatusChange?: (
    documentId: string,
    status: ProcessingStatus
  ) => void;
}

// Memoized document item for performance
const DocumentItem = memo<{
  index: number;
  style: React.CSSProperties;
  data: {
    documents: Document[];
    selectedId?: string;
    onSelect: (document: Document) => void;
    onStatusChange: (id: string, status: ProcessingStatus) => void;
  };
}>(({ index, style, data }) => {
  const document = data.documents[index];
  const isSelected = data.selectedId === document.id;

  return (
    <div style={style}>
      <Suspense fallback={<DocumentSkeleton />}>
        <DocumentRow
          document={document}
          isSelected={isSelected}
          onSelect={() => data.onSelect(document)}
          onStatusChange={data.onStatusChange}
        />
      </Suspense>
    </div>
  );
});

DocumentItem.displayName = 'DocumentItem';

// Virtualized list component with infinite scrolling
const VirtualizedDocumentList = memo<{
  documents: Document[];
  selectedId?: string;
  onSelect: (document: Document) => void;
  onStatusChange: (id: string, status: ProcessingStatus) => void;
  onLoadMore: () => void;
  hasMore: boolean;
  isLoading: boolean;
}>(
  ({
    documents,
    selectedId,
    onSelect,
    onStatusChange,
    onLoadMore,
    hasMore,
    isLoading,
  }) => {
    const listRef = useRef<List>(null);
    const [scrollPosition, setScrollPosition] = useState(0);

    // Memoized item data to prevent unnecessary re-renders
    const itemData = useMemo(
      () => ({
        documents,
        selectedId,
        onSelect,
        onStatusChange,
      }),
      [documents, selectedId, onSelect, onStatusChange]
    );

    // Handle scroll events with throttling — ref stores instance so we can cancel on dep changes
    const throttleRef = useRef<ReturnType<typeof throttle>>();
    useEffect(() => {
      throttleRef.current = throttle((e: React.UIEvent<HTMLDivElement>) => {
        const element = e.currentTarget;
        setScrollPosition(element.scrollTop);

        // Check if near bottom for infinite loading
        if (
          element.scrollHeight - element.scrollTop - element.clientHeight <
            1000 &&
          hasMore &&
          !isLoading
        ) {
          onLoadMore();
        }
      }, THROTTLE_DELAY);
      return () => {
        throttleRef.current?.cancel();
      };
    }, [hasMore, isLoading, onLoadMore]);

    const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
      throttleRef.current?.(e);
    }, []);

    // Render item function
    const renderItem = useCallback(
      ({ index, style }: { index: number; style: React.CSSProperties }) => (
        <DocumentItem
          key={documents[index]?.id || `item-${index}`}
          index={index}
          style={style}
          data={itemData}
        />
      ),
      [documents, itemData]
    );

    return (
      <div
        className="h-full overflow-auto"
        onScroll={handleScroll}
        style={{ contain: 'strict' }}
      >
        <List
          ref={listRef}
          height={
            typeof window !== 'undefined' ? window.innerHeight - 200 : 600
          }
          itemCount={documents.length}
          itemSize={ITEM_HEIGHT}
          itemData={itemData}
          overscanCount={BUFFER_SIZE}
          className="virtualized-list"
          style={{ contain: 'strict' }}
        >
          {renderItem}
        </List>

        {/* Loading indicator for infinite scroll */}
        {isLoading && documents.length > 0 && (
          <div className="flex justify-center py-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
          </div>
        )}

        {/* End of content indicator */}
        {!hasMore && documents.length > 0 && (
          <div className="text-center py-4 text-gray-500">End of documents</div>
        )}
      </div>
    );
  }
);

VirtualizedDocumentList.displayName = 'VirtualizedDocumentList';

// Main optimized document list component
export const OptimizedDocumentList: React.FC<OptimizedDocumentListProps> = ({
  organizationId,
  filters = {},
  onDocumentSelect,
  onDocumentStatusChange,
}) => {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string>();
  const { subscribe, unsubscribe, isConnected } = useWebSocketConnection();

  // Optimized search with debouncing — ref stores instance so we can flush/cancel on dep changes
  const debounceRef = useRef<ReturnType<typeof debounce>>();
  useEffect(() => {
    debounceRef.current = debounce((searchTerm: string) => {
      queryClient.invalidateQueries({
        queryKey: ['documents', organizationId],
      });
    }, DEBOUNCE_DELAY);
    return () => {
      debounceRef.current?.cancel();
    };
  }, [queryClient, organizationId]);

  // Infinite query for documents with performance monitoring
  const {
    data,
    isLoading,
    isError,
    error,
    hasNextPage,
    fetchNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['documents', organizationId, filters],
    queryFn: async ({ pageParam = 0, queryKey }) => {
      const [, orgId, currentFilters] = queryKey;

      const startTime = performance.now();

      const result = await api.post('/documents/search', {
        organizationId: orgId,
        filters: currentFilters,
        pagination: {
          page: pageParam,
          limit: BATCH_SIZE,
        },
      });

      // Performance monitoring
      const endTime = performance.now();
      performanceMonitor.recordQuery('documents_search', endTime - startTime);

      return result;
    },
    getNextPageParam: (lastPage, allPages) => {
      if (lastPage.hasMore) {
        return allPages.length;
      }
      return undefined;
    },
    staleTime: 30 * 1000, // 30 seconds
    cacheTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: false,
    refetchOnReconnect: true,
  });

  // Flatten all pages into a single array
  const documents = useMemo(
    () => data?.pages.flatMap((page) => page.documents) ?? [],
    [data]
  );

  // WebSocket subscription for real-time updates
  useEffect(() => {
    if (!isConnected) return;

    const handleStatusUpdate = (message: any) => {
      const { documentId, status } = message.data;

      // Update the document in cache
      queryClient.setQueryData(
        ['documents', organizationId, filters],
        (oldData: any) => {
          if (!oldData) return oldData;

          return {
            ...oldData,
            pages: oldData.pages.map((page: any) => ({
              ...page,
              documents: page.documents.map((doc: Document) =>
                doc.id === documentId ? { ...doc, status } : doc
              ),
            })),
          };
        }
      );

      // Call callback if provided
      if (onDocumentStatusChange) {
        onDocumentStatusChange(documentId, status);
      }
    };

    subscribe('document_status_updates', handleStatusUpdate);

    return () => {
      unsubscribe('document_status_updates', handleStatusUpdate);
    };
  }, [
    isConnected,
    queryClient,
    organizationId,
    filters,
    onDocumentStatusChange,
    subscribe,
    unsubscribe,
  ]);

  // Handle document selection with performance tracking
  const handleDocumentSelect = useCallback(
    (document: Document) => {
      const startTime = performance.now();

      setSelectedId(document.id);
      onDocumentSelect?.(document);

      const endTime = performance.now();
      performanceMonitor.recordInteraction(
        'document_select',
        endTime - startTime
      );
    },
    [onDocumentSelect]
  );

  // Handle status change with optimistic updates
  const handleStatusChange = useCallback(
    (documentId: string, status: ProcessingStatus) => {
      // Optimistic update
      queryClient.setQueryData(
        ['documents', organizationId, filters],
        (oldData: any) => {
          if (!oldData) return oldData;

          return {
            ...oldData,
            pages: oldData.pages.map((page: any) => ({
              ...page,
              documents: page.documents.map((doc: Document) =>
                doc.id === documentId ? { ...doc, status } : doc
              ),
            })),
          };
        }
      );

      onDocumentStatusChange?.(documentId, status);
    },
    [queryClient, organizationId, filters, onDocumentStatusChange]
  );

  // Handle search input with debouncing
  const handleSearchChange = useCallback((searchTerm: string) => {
    debounceRef.current?.(searchTerm);
  }, []);

  // Memoized load more function
  const handleLoadMore = useCallback(() => {
    if (hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // Error boundary fallback
  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-red-500">
        <div className="text-lg font-semibold">Error loading documents</div>
        <div className="text-sm">{error?.message || 'Unknown error'}</div>
        <button
          onClick={() =>
            queryClient.invalidateQueries(['documents', organizationId])
          }
          className="mt-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Retry
        </button>
      </div>
    );
  }

  // Initial loading state
  if (isLoading && !documents.length) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 10 }, (_, i) => (
          <Suspense key={i} fallback={<DocumentSkeleton />}>
            <DocumentSkeleton />
          </Suspense>
        ))}
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Search and filter bar */}
      <div className="p-4 border-b border-gray-200 bg-white">
        <input
          type="text"
          placeholder="Search documents..."
          onChange={(e) => handleSearchChange(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {/* Virtualized document list */}
      <div className="flex-1">
        <VirtualizedDocumentList
          documents={documents}
          selectedId={selectedId}
          onSelect={handleDocumentSelect}
          onStatusChange={handleStatusChange}
          onLoadMore={handleLoadMore}
          hasMore={!!hasNextPage}
          isLoading={isFetchingNextPage}
        />
      </div>

      {/* Connection status indicator */}
      <div className="p-2 border-t border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>
            {documents.length} documents loaded
            {isFetchingNextPage && ' (loading more...)'}
          </span>
          <span
            className={`flex items-center ${isConnected ? 'text-green-500' : 'text-red-500'}`}
          >
            <span
              className={`w-2 h-2 rounded-full mr-1 ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}
            />
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>
    </div>
  );
};

OptimizedDocumentList.displayName = 'OptimizedDocumentList';

export default OptimizedDocumentList;
