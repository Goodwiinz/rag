import React, { memo, useCallback, useMemo } from 'react';
import {
  DocumentProcessingState,
  ProcessingStage,
} from '@/types/realtime-processing';
import { FileIcon } from './FileIcon';
import { ProcessingProgressBar } from './ProcessingProgressBar';
import { StageIndicators } from './StageIndicators';
import { ActionButtons } from './ActionButtons';
import { ErrorDisplay } from './ErrorDisplay';
import { cn } from '@/lib/utils';
import { formatFileSize, formatDuration } from '@/lib/formatters';

interface DocumentProcessingCardProps {
  document: DocumentProcessingState;
  isSelected?: boolean;
  onSelect?: (documentId: string, selected: boolean) => void;
  compact?: boolean;
  showActions?: boolean;
  showProgress?: boolean;
  showStages?: boolean;
  className?: string;
  onRetry?: (documentId: string) => void;
  onPause?: (documentId: string) => void;
  onResume?: (documentId: string) => void;
  onCancel?: (documentId: string) => void;
  onDownload?: (documentId: string) => void;
  onClick?: (document: DocumentProcessingState) => void;
  onErrorClick?: (error: string) => void;
}

interface ProcessingCardTheme {
  container: string;
  selected: string;
  progress: string;
  error: string;
  success: string;
  warning: string;
  info: string;
}

const PROCESSING_THEMES: Record<
  DocumentProcessingState['status'],
  ProcessingCardTheme
> = {
  queued: {
    container: 'bg-[var(--nous-bg-2)] border-border',
    selected: 'ring-[var(--nous-sol)] bg-[var(--nous-bg-3)]',
    progress: 'bg-[var(--nous-border-1)]',
    error: '',
    success: '',
    warning: '',
    info: 'text-foreground',
  },
  uploading: {
    container: 'bg-[var(--nous-sol)]/10 border-[var(--nous-sol)]/30',
    selected: 'ring-[var(--nous-sol)] bg-[var(--nous-sol)]/15',
    progress: 'bg-[var(--nous-sol)]',
    error: '',
    success: '',
    warning: '',
    info: 'text-[var(--nous-sol-safe)]',
  },
  processing: {
    container: 'bg-[var(--nous-corona)]/10 border-[var(--nous-corona)]/30',
    selected: 'ring-[var(--nous-corona)] bg-[var(--nous-corona)]/15',
    progress: 'bg-[var(--nous-corona)]',
    error: '',
    success: '',
    warning: '',
    info: 'text-[var(--nous-corona)]',
  },
  completed: {
    container: 'bg-[var(--nous-terra)]/10 border-[var(--nous-terra)]/30',
    selected: 'ring-[var(--nous-terra)] bg-[var(--nous-terra)]/15',
    progress: 'bg-[var(--nous-terra)]',
    error: '',
    success: 'text-[var(--nous-terra)]',
    warning: '',
    info: '',
  },
  failed: {
    container: 'bg-[var(--nous-mars)]/10 border-[var(--nous-mars)]/30',
    selected: 'ring-[var(--nous-mars)] bg-[var(--nous-mars)]/15',
    progress: 'bg-[var(--nous-mars)]',
    error: 'text-[var(--nous-mars)]',
    success: '',
    warning: '',
    info: '',
  },
  paused: {
    container: 'bg-[var(--nous-corona)]/10 border-[var(--nous-corona)]/30',
    selected: 'ring-[var(--nous-corona)] bg-[var(--nous-corona)]/15',
    progress: 'bg-[var(--nous-corona)]',
    error: '',
    success: '',
    warning: 'text-[var(--nous-corona)]',
    info: '',
  },
  cancelled: {
    container: 'bg-[var(--nous-bg-3)] border-border',
    selected: 'ring-[var(--nous-border-1)] bg-[var(--nous-bg-3)]',
    progress: 'bg-[var(--nous-border-1)]',
    error: '',
    success: '',
    warning: '',
    info: 'text-foreground',
  },
};

// Helper to get human-readable stage name
const getStageDisplayName = (stage: ProcessingStage['name']): string => {
  const stageNames: Record<string, string> = {
    upload: 'Upload',
    validation: 'Validation',
    ocr: 'OCR Processing',
    transcription: 'Transcription',
    frame_extraction: 'Frame Extraction',
    entity_extraction: 'Entity Extraction',
    embedding: 'Vector Embedding',
    indexing: 'Indexing',
    knowledge_graph: 'Knowledge Graph',
    quality_check: 'Quality Check',
    finalization: 'Finalization',
  };
  return stageNames[stage] || stage;
};

// Helper to get stage icon
const getStageIcon = (stage: ProcessingStage['name']): string => {
  const stageIcons: Record<string, string> = {
    upload: '⬆️',
    validation: '✅',
    ocr: '📄',
    transcription: '🎵',
    frame_extraction: '🎬',
    entity_extraction: '🏷️',
    embedding: '🔢',
    indexing: '📚',
    knowledge_graph: '🕸️',
    quality_check: '🔍',
    finalization: '🎉',
  };
  return stageIcons[stage] || '⏳';
};

export const DocumentProcessingCard: React.FC<DocumentProcessingCardProps> =
  memo(
    ({
      document,
      isSelected = false,
      onSelect,
      compact = false,
      showActions = true,
      showProgress = true,
      showStages = false,
      className = '',
      onRetry,
      onPause,
      onResume,
      onCancel,
      onDownload,
      onClick,
      onErrorClick,
    }) => {
      const theme = PROCESSING_THEMES[document.status];

      // Handle selection change
      const handleSelectionChange = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
          e.stopPropagation();
          onSelect?.(document.id, e.target.checked);
        },
        [document.id, onSelect]
      );

      // Handle card click
      const handleCardClick = useCallback(() => {
        onClick?.(document);
      }, [document, onClick]);

      // Handle action clicks
      const handleRetry = useCallback(
        (e: React.MouseEvent) => {
          e.stopPropagation();
          onRetry?.(document.id);
        },
        [document.id, onRetry]
      );

      const handlePause = useCallback(
        (e: React.MouseEvent) => {
          e.stopPropagation();
          onPause?.(document.id);
        },
        [document.id, onPause]
      );

      const handleResume = useCallback(
        (e: React.MouseEvent) => {
          e.stopPropagation();
          onResume?.(document.id);
        },
        [document.id, onResume]
      );

      const handleCancel = useCallback(
        (e: React.MouseEvent) => {
          e.stopPropagation();
          onCancel?.(document.id);
        },
        [document.id, onCancel]
      );

      const handleDownload = useCallback(
        (e: React.MouseEvent) => {
          e.stopPropagation();
          onDownload?.(document.id);
        },
        [document.id, onDownload]
      );

      const handleErrorClick = useCallback(
        (e: React.MouseEvent) => {
          e.stopPropagation();
          onErrorClick?.(document.error || '');
        },
        [document.error, onErrorClick]
      );

      // Memoize formatted values
      const formattedFileSize = useMemo(() => {
        return formatFileSize(document.metadata.fileSize);
      }, [document.metadata.fileSize]);

      const formattedDuration = useMemo(() => {
        if (document.metadata.duration) {
          return formatDuration(document.metadata.duration);
        }
        return null;
      }, [document.metadata.duration]);

      const timeRemaining = useMemo(() => {
        if (document.metadata.estimatedTimeRemaining) {
          return formatDuration(document.metadata.estimatedTimeRemaining);
        }
        return null;
      }, [document.metadata.estimatedTimeRemaining]);

      // Determine if card should show error display
      const hasError = document.status === 'failed' && document.error;

      if (compact) {
        return (
          <div
            className={cn(
              'flex items-center justify-between p-3 border rounded-lg cursor-pointer transition-all hover:shadow-md',
              theme.container,
              isSelected && theme.selected,
              className
            )}
            onClick={handleCardClick}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && handleCardClick()}
            aria-label={`Document: ${document.filename}`}
          >
            <div className="flex items-center space-x-3">
              {/* Checkbox */}
              {onSelect && (
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={handleSelectionChange}
                  className="h-4 w-4 text-[var(--nous-sol)] focus:ring-[var(--nous-sol)] border-border rounded"
                  aria-label={`Select ${document.filename}`}
                />
              )}

              {/* File Icon */}
              <FileIcon
                fileType={document.fileType}
                size="sm"
                status={document.status}
              />

              {/* Document Info */}
              <div className="min-w-0 flex-1">
                <h3 className="text-sm font-medium text-foreground truncate">
                  {document.filename}
                </h3>
                <p className="text-xs text-muted-foreground">
                  {formattedFileSize} •{' '}
                  {timeRemaining
                    ? `${timeRemaining} remaining`
                    : document.status}
                </p>
              </div>

              {/* Progress */}
              {showProgress && document.overallProgress > 0 && (
                <div className="w-20">
                  <ProcessingProgressBar
                    progress={document.overallProgress}
                    size="sm"
                    color={theme.progress}
                    showPercentage={false}
                  />
                </div>
              )}

              {/* Status Icon */}
              <div
                className={cn(
                  'text-sm font-medium',
                  theme.info || theme.error || theme.success
                )}
              >
                {document.status}
              </div>
            </div>
          </div>
        );
      }

      return (
        <div
          className={cn(
            'bg-background border rounded-lg p-4 cursor-pointer transition-all hover:shadow-lg focus:outline-none focus:ring-2',
            theme.container,
            isSelected && theme.selected,
            className
          )}
          onClick={handleCardClick}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && handleCardClick()}
          aria-label={`Document: ${document.filename}`}
        >
          {/* Header */}
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-start space-x-3 flex-1">
              {/* Checkbox */}
              {onSelect && (
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={handleSelectionChange}
                  className="h-4 w-4 text-[var(--nous-sol)] focus:ring-[var(--nous-sol)] border-border rounded mt-1"
                  aria-label={`Select ${document.filename}`}
                />
              )}

              {/* File Icon and Info */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center space-x-2">
                  <FileIcon
                    fileType={document.fileType}
                    size="md"
                    status={document.status}
                  />
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-medium text-foreground truncate">
                      {document.filename}
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      {formattedFileSize}
                      {formattedDuration && ` • ${formattedDuration}`}
                    </p>
                  </div>
                </div>
              </div>

              {/* Actions */}
              {showActions && (
                <ActionButtons
                  document={document}
                  onRetry={handleRetry}
                  onPause={handlePause}
                  onResume={handleResume}
                  onCancel={handleCancel}
                  onDownload={handleDownload}
                  compact={false}
                />
              )}
            </div>
          </div>

          {/* Progress Bar */}
          {showProgress && document.overallProgress > 0 && (
            <div className="mb-3">
              <div className="flex justify-between items-center mb-1">
                <span className="text-xs text-foreground">
                  Overall Progress
                </span>
                <span className="text-xs font-medium text-foreground">
                  {Math.round(document.overallProgress)}%
                </span>
              </div>
              <ProcessingProgressBar
                progress={document.overallProgress}
                size="md"
                color={theme.progress}
                showPercentage={false}
              />
              {timeRemaining && (
                <p className="text-xs text-muted-foreground mt-1">
                  Estimated time remaining: {timeRemaining}
                </p>
              )}
            </div>
          )}

          {/* Stage Indicators */}
          {showStages && document.stages.length > 0 && (
            <div className="mb-3">
              <StageIndicators
                stages={document.stages}
                currentStage={document.currentStage}
                compact={false}
              />
            </div>
          )}

          {/* Current Stage Information */}
          {document.currentStage && (
            <div className="mb-3">
              <div className="flex items-center space-x-2">
                <span className="text-lg">
                  {getStageIcon(document.currentStage.id)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-foreground">
                    {getStageDisplayName(document.currentStage.name)}
                  </p>
                  <p className="text-xs text-foreground">
                    {document.currentStage.description}
                  </p>
                </div>
                {document.currentStage.progress > 0 && (
                  <span className="text-sm font-medium text-foreground">
                    {Math.round(document.currentStage.progress)}%
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Error Display */}
          {hasError && (
            <div className="mt-3">
              <ErrorDisplay
                error={document.error}
                onRetry={handleRetry}
                onErrorClick={handleErrorClick}
                compact={false}
                retryCount={document.retryCount}
                canRetry={document.canRetry}
              />
            </div>
          )}

          {/* Metadata */}
          <div className="mt-3 pt-3 border-t border-border">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <div className="flex items-center space-x-4">
                <span>
                  Uploaded:{' '}
                  {new Date(
                    document.metadata.uploadStartedAt
                  ).toLocaleTimeString()}
                </span>
                {document.retryCount > 0 && (
                  <span className="text-[var(--nous-corona)]">
                    Retry #{document.retryCount}
                  </span>
                )}
              </div>
              <div
                className={cn(
                  'font-medium uppercase tracking-wide',
                  theme.info || theme.error || theme.success
                )}
              >
                {document.status}
              </div>
            </div>
          </div>
        </div>
      );
    }
  );

DocumentProcessingCard.displayName = 'DocumentProcessingCard';
