import React, { memo, useMemo, useCallback, useRef, useEffect } from 'react';
import { FixedSizeList as List } from 'react-window';
import { DocumentProcessingState } from '@/types/realtime-processing';
import { DocumentProcessingCard } from './DocumentProcessingCard';
import { ListSkeletonLoader } from './ListSkeletonLoader';
import { cn } from '@/lib/utils';

interface VirtualizedDocumentListProps {
  documents: DocumentProcessingState[];
  selectedDocuments: string[];
  isLoading?: boolean;
  height?: number;
  itemSize?: number;
  compact?: boolean;
  showActions?: boolean;
  showProgress?: boolean;
  showStages?: boolean;
  className?: string;
  onItemClick?: (document: DocumentProcessingState) => void;
  onItemSelect?: (documentId: string, selected: boolean) => void;
  onRetry?: (documentId: string) => void;
  onPause?: (documentId: string) => void;
  onResume?: (documentId: string) => void;
  onCancel?: (documentId: string) => void;
  onDownload?: (documentId: string) => void;
  onErrorClick?: (error: string) => void;
  scrollToIndex?: number;
  threshold?: number;
  overscanCount?: number;
}

interface DocumentItemData {
  documents: DocumentProcessingState[];
  selectedDocuments: string[];
  compact: boolean;
  showActions: boolean;
  showProgress: boolean;
  showStages: boolean;
  onItemClick?: (document: DocumentProcessingState) => void;
  onItemSelect?: (documentId: string, selected: boolean) => void;
  onRetry?: (documentId: string) => void;
  onPause?: (documentId: string) => void;
  onResume?: (documentId: string) => void;
  onCancel?: (documentId: string) => void;
  onDownload?: (documentId: string) => void;
  onErrorClick?: (error: string) => void;
}

// Virtualized list item component
const DocumentListItem: React.FC<{
  index: number;
  style: React.CSSProperties;
  data: DocumentItemData;
}> = memo(({ index, style, data }) => {
  const document = data.documents[index];
  const isSelected = data.selectedDocuments.includes(document.id);

  const handleSelect = useCallback(
    (documentId: string, selected: boolean) => {
      data.onItemSelect?.(documentId, selected);
    },
    [data.onItemSelect]
  );

  const handleRetry = useCallback(
    (documentId: string) => {
      data.onRetry?.(documentId);
    },
    [data.onRetry]
  );

  const handlePause = useCallback(
    (documentId: string) => {
      data.onPause?.(documentId);
    },
    [data.onPause]
  );

  const handleResume = useCallback(
    (documentId: string) => {
      data.onResume?.(documentId);
    },
    [data.onResume]
  );

  const handleCancel = useCallback(
    (documentId: string) => {
      data.onCancel?.(documentId);
    },
    [data.onCancel]
  );

  const handleDownload = useCallback(
    (documentId: string) => {
      data.onDownload?.(documentId);
    },
    [data.onDownload]
  );

  const handleErrorClick = useCallback(
    (error: string) => {
      data.onErrorClick?.(error);
    },
    [data.onErrorClick]
  );

  return (
    <div style={style}>
      <DocumentProcessingCard
        document={document}
        isSelected={isSelected}
        onSelect={handleSelect}
        compact={data.compact}
        showActions={data.showActions}
        showProgress={data.showProgress}
        showStages={data.showStages}
        onClick={data.onItemClick}
        onRetry={handleRetry}
        onPause={handlePause}
        onResume={handleResume}
        onCancel={handleCancel}
        onDownload={handleDownload}
        onErrorClick={handleErrorClick}
      />
    </div>
  );
});

DocumentListItem.displayName = 'DocumentListItem';

// Loading placeholder for virtualized items
const LoadingPlaceholder: React.FC<{
  index: number;
  style: React.CSSProperties;
  compact: boolean;
}> = memo(({ index, style, compact }) => {
  return (
    <div style={style}>
      <ListSkeletonLoader count={1} compact={compact} className="m-2" />
    </div>
  );
});

LoadingPlaceholder.displayName = 'LoadingPlaceholder';

export const VirtualizedDocumentList: React.FC<VirtualizedDocumentListProps> =
  memo(
    ({
      documents,
      selectedDocuments,
      isLoading = false,
      height = 600,
      itemSize = 120,
      compact = false,
      showActions = true,
      showProgress = true,
      showStages = false,
      className = '',
      onItemClick,
      onItemSelect,
      onRetry,
      onPause,
      onResume,
      onCancel,
      onDownload,
      onErrorClick,
      scrollToIndex,
      threshold = 100,
      overscanCount = 5,
    }) => {
      const listRef = useRef<List<DocumentItemData>>(null);
      const itemCount = documents.length;

      // Memoize item data to prevent unnecessary re-renders
      const itemData = useMemo<DocumentItemData>(
        () => ({
          documents,
          selectedDocuments,
          compact,
          showActions,
          showProgress,
          showStages,
          onItemClick,
          onItemSelect,
          onRetry,
          onPause,
          onResume,
          onCancel,
          onDownload,
          onErrorClick,
        }),
        [
          documents,
          selectedDocuments,
          compact,
          showActions,
          showProgress,
          showStages,
          onItemClick,
          onItemSelect,
          onRetry,
          onPause,
          onResume,
          onCancel,
          onDownload,
          onErrorClick,
        ]
      );

      // Handle scroll to index
      useEffect(() => {
        if (scrollToIndex !== undefined && listRef.current) {
          listRef.current.scrollToItem(scrollToIndex, 'center');
        }
      }, [scrollToIndex]);

      // Memoize item renderer
      const renderItem = useCallback(
        ({ index, style }: { index: number; style: React.CSSProperties }) => {
          if (isLoading && index >= documents.length) {
            return (
              <LoadingPlaceholder
                index={index}
                style={style}
                compact={compact}
              />
            );
          }

          return (
            <DocumentListItem index={index} style={style} data={itemData} />
          );
        },
        [isLoading, documents.length, compact, itemData]
      );

      // Memoize item count including loading placeholders
      const displayItemCount = useMemo(() => {
        return isLoading ? itemCount + 5 : itemCount; // Show 5 loading placeholders during loading
      }, [itemCount, isLoading]);

      // Show empty state
      if (itemCount === 0 && !isLoading) {
        return (
          <div
            className={cn(
              'flex flex-col items-center justify-center p-8 text-muted-foreground',
              className
            )}
          >
            <div className="w-16 h-16 mb-4 text-muted-foreground">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-foreground mb-2">
              No documents found
            </h3>
            <p className="text-sm text-muted-foreground text-center max-w-md">
              No documents match your current filters. Try adjusting your search
              criteria or upload new documents.
            </p>
          </div>
        );
      }

      // For small lists, don't use virtualization
      if (itemCount < threshold && !isLoading) {
        return (
          <div className={cn('space-y-3', className)}>
            {documents.map((document) => (
              <DocumentProcessingCard
                key={document.id}
                document={document}
                isSelected={selectedDocuments.includes(document.id)}
                onSelect={onItemSelect}
                compact={compact}
                showActions={showActions}
                showProgress={showProgress}
                showStages={showStages}
                onClick={onItemClick}
                onRetry={onRetry}
                onPause={onPause}
                onResume={onResume}
                onCancel={onCancel}
                onDownload={onDownload}
                onErrorClick={onErrorClick}
              />
            ))}
          </div>
        );
      }

      // Virtualized list for large datasets
      return (
        <div className={cn('border border-border rounded-lg', className)}>
          <List
            ref={listRef}
            height={height}
            itemCount={displayItemCount}
            itemSize={compact ? 80 : itemSize}
            itemData={itemData}
            overscanCount={overscanCount}
            className="scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100"
            // Performance optimizations
            useIsScrolling={false}
            initialScrollOffset={0}
            onItemsRendered={({ visibleStartIndex, visibleStopIndex }) => {
              // Trigger analytics or lazy loading if needed
              // console.log(`Rendering items ${visibleStartIndex} to ${visibleStopIndex}`);
            }}
          >
            {renderItem}
          </List>

          {/* Loading overlay for skeleton loaders */}
          {isLoading && itemCount === 0 && (
            <div className="absolute inset-0 pointer-events-none">
              <ListSkeletonLoader count={10} compact={compact} />
            </div>
          )}
        </div>
      );
    }
  );

VirtualizedDocumentList.displayName = 'VirtualizedDocumentList';

// Utility component for skeleton loading states
export const ListSkeletonLoader: React.FC<{
  count?: number;
  compact?: boolean;
  className?: string;
}> = memo(({ count = 5, compact = false, className = '' }) => {
  return (
    <div className={cn('space-y-3', className)}>
      {Array.from({ length: count }, (_, index) => (
        <div
          key={index}
          className={cn(
            'border border-border rounded-lg p-4 animate-pulse',
            compact ? 'p-3' : 'p-4'
          )}
        >
          <div className="flex items-center space-x-3">
            <div className="w-5 h-5 bg-gray-300 rounded"></div>
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-gray-300 rounded w-3/4"></div>
              <div className="h-3 bg-gray-200 rounded w-1/2"></div>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-20 h-2 bg-gray-200 rounded"></div>
              <div className="w-16 h-6 bg-gray-300 rounded"></div>
            </div>
          </div>
          {!compact && (
            <div className="mt-3 space-y-2">
              <div className="h-2 bg-gray-200 rounded w-full"></div>
              <div className="h-2 bg-gray-200 rounded w-4/5"></div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
});

ListSkeletonLoader.displayName = 'ListSkeletonLoader';
