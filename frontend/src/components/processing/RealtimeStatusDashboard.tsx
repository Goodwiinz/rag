import { IconButton } from '@/components/ui/icon-button';
/**
 * Real-time Status Dashboard Component
 *
 * Comprehensive dashboard for monitoring document processing status
 * with real-time updates, performance metrics, and management controls.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  DocumentTextIcon,
  ClockIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  XCircleIcon,
  PauseIcon,
  PlayIcon,
  ArrowPathIcon,
  TrashIcon,
  ServerIcon,
  CpuChipIcon,
  CircleStackIcon,
  SignalIcon,
  BellIcon,
  FunnelIcon,
  ListBulletIcon,
  Squares2X2Icon,
  ArrowsUpDownIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import {
  useRealtimeProcessing,
  useConnectionStatus,
} from '@/hooks/useRealtimeProcessing';
import { useRealtimeProcessingStore } from '@/store/realtimeProcessingStore';
import {
  DocumentProcessingState,
  WebSocketConnectionState,
  ProcessingQueue,
  SystemMetrics,
} from '@/types/realtime-processing';
import { cn } from '@/lib/utils';
import {
  formatDuration,
  formatFileSize,
  formatNumber,
} from '@/utils/formatUtils';

interface RealtimeStatusDashboardProps {
  className?: string;
  showSystemMetrics?: boolean;
  showFilters?: boolean;
  maxDocuments?: number;
  autoRefresh?: boolean;
}

interface DocumentCardProps {
  document: DocumentProcessingState;
  selected: boolean;
  onSelect: (documentId: string) => void;
  onPause: (documentId: string) => void;
  onResume: (documentId: string) => void;
  onCancel: (documentId: string) => void;
  onRetry: (documentId: string) => void;
  compact?: boolean;
}

interface StatusIndicatorProps {
  status: DocumentProcessingState['status'];
  className?: string;
}

interface ProgressRingProps {
  progress: number;
  size?: number;
  strokeWidth?: number;
  className?: string;
}

interface StageProgressProps {
  stages: DocumentProcessingState['stages'];
  currentStage: DocumentProcessingState['currentStage'];
  compact?: boolean;
}

// Helper Components
const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  status,
  className,
}) => {
  const statusConfig = {
    queued: {
      icon: ClockIcon,
      color: 'text-muted-foreground',
      bgColor: 'bg-[var(--nous-bg-3)]',
    },
    uploading: {
      icon: ArrowPathIcon,
      color: 'text-[var(--nous-sol-safe)]',
      bgColor: 'bg-[var(--nous-sol)]/15',
    },
    processing: {
      icon: ArrowPathIcon,
      color: 'text-[var(--nous-sol-safe)]',
      bgColor: 'bg-[var(--nous-sol)]/15',
    },
    completed: {
      icon: CheckCircleIcon,
      color: 'text-[var(--nous-terra)]',
      bgColor: 'bg-[var(--nous-terra)]/15',
    },
    failed: {
      icon: XCircleIcon,
      color: 'text-[var(--nous-mars)]',
      bgColor: 'bg-[var(--nous-mars)]/15',
    },
    paused: {
      icon: PauseIcon,
      color: 'text-[var(--nous-corona)]',
      bgColor: 'bg-[var(--nous-corona)]/15',
    },
    cancelled: {
      icon: XMarkIcon,
      color: 'text-muted-foreground',
      bgColor: 'bg-[var(--nous-bg-3)]',
    },
  };

  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <div className={cn('inline-flex items-center space-x-1', className)}>
      <div className={cn('p-1 rounded-full', config.bgColor)}>
        <Icon className={cn('h-4 w-4', config.color)} />
      </div>
      <span className={cn('text-sm font-medium', config.color)}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    </div>
  );
};

const ProgressRing: React.FC<ProgressRingProps> = ({
  progress,
  size = 60,
  strokeWidth = 4,
  className,
}) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const strokeDashoffset = circumference - (progress / 100) * circumference;

  return (
    <div className={cn('relative', className)}>
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth={strokeWidth}
          fill="none"
          className="text-muted-foreground"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className="text-[var(--nous-sol-safe)] transition-all duration-500 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-sm font-semibold">{Math.round(progress)}%</span>
      </div>
    </div>
  );
};

const StageProgress: React.FC<StageProgressProps> = ({
  stages,
  currentStage,
  compact = false,
}) => {
  if (compact) {
    return (
      <div className="flex space-x-1">
        {stages.map((stage, index) => {
          const isActive = stage.id === currentStage.id;
          const isCompleted = stage.status === 'completed';
          const hasError = stage.status === 'failed';

          return (
            <div
              key={stage.id}
              className={cn(
                'flex-1 h-1 rounded-full transition-all duration-300',
                isCompleted
                  ? 'bg-[var(--nous-terra)]'
                  : hasError
                    ? 'bg-[var(--nous-mars)]'
                    : isActive
                      ? 'bg-[var(--nous-sol)]'
                      : 'bg-[var(--nous-bg-3)]'
              )}
              title={stage.name}
            />
          );
        })}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {stages.map((stage, index) => {
        const isActive = stage.id === currentStage.id;
        const isCompleted = stage.status === 'completed';
        const hasError = stage.status === 'failed';

        return (
          <div key={stage.id} className="flex items-center space-x-3">
            <div
              className={cn(
                'w-4 h-4 rounded-full border-2 flex items-center justify-center',
                isCompleted
                  ? 'border-[var(--nous-terra)] bg-[var(--nous-terra)]'
                  : hasError
                    ? 'border-[var(--nous-mars)] bg-[var(--nous-mars)]'
                    : isActive
                      ? 'border-[var(--nous-sol)] bg-[var(--nous-sol)]'
                      : 'border-border'
              )}
            >
              {isCompleted && (
                <svg
                  className="w-2 h-2 text-white"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
              )}
            </div>
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <span
                  className={cn(
                    'text-sm font-medium',
                    isActive ? 'text-[var(--nous-sol-safe)]' : 'text-foreground'
                  )}
                >
                  {stage.name}
                </span>
                <span className="text-xs text-muted-foreground">
                  {stage.duration
                    ? `${(stage.duration / 1000).toFixed(1)}s`
                    : '-'}
                </span>
              </div>
              {isActive && (
                <div className="mt-1 w-full bg-[var(--nous-bg-3)] rounded-full h-1">
                  <div
                    className="bg-[var(--nous-sol)] h-1 rounded-full transition-all duration-300"
                    style={{ width: `${stage.progress}%` }}
                  />
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const DocumentCard: React.FC<DocumentCardProps> = ({
  document,
  selected,
  onSelect,
  onPause,
  onResume,
  onCancel,
  onRetry,
  compact = false,
}) => {
  const [showDetails, setShowDetails] = useState(false);

  const handleAction = (action: () => void) => {
    action();
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className={cn(
        'bg-card rounded-lg border border-border shadow-sm hover:shadow-md transition-all duration-200',
        selected && 'ring-2 ring-[var(--nous-sol)] ring-offset-2',
        compact ? 'p-3' : 'p-4'
      )}
    >
      <div className="flex items-start space-x-3">
        {/* Progress indicator */}
        <div className="flex-shrink-0">
          <ProgressRing
            progress={document.overallProgress}
            size={compact ? 40 : 50}
            strokeWidth={compact ? 3 : 4}
          />
        </div>

        {/* Document info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <h3
              className={cn(
                'text-sm font-medium text-foreground truncate',
                compact && 'text-xs'
              )}
            >
              {document.filename}
            </h3>
            <div className="flex items-center space-x-2 ml-2">
              <StatusIndicator status={document.status} />
              <input
                type="checkbox"
                checked={selected}
                onChange={() => onSelect(document.id)}
                className="h-4 w-4 text-[var(--nous-sol-safe)] focus:ring-[var(--nous-sol)] border-border rounded"
              />
            </div>
          </div>

          {/* File info */}
          <div
            className={cn(
              'flex items-center space-x-4 mt-1 text-xs text-muted-foreground',
              compact && 'mt-0'
            )}
          >
            <span>{document.fileType.toUpperCase()}</span>
            <span>{formatFileSize(document.metadata.fileSize)}</span>
            {document.metadata.duration && (
              <span>{formatDuration(document.metadata.duration)}</span>
            )}
            {document.retryCount > 0 && (
              <span className="text-[var(--nous-corona)]">
                Retry {document.retryCount}
              </span>
            )}
          </div>

          {/* Stage progress */}
          {!compact && (
            <div className="mt-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm text-foreground">
                  {document.currentStage.name}
                </span>
                <span className="text-xs text-muted-foreground">
                  {document.currentStage.progress}%
                </span>
              </div>
              <StageProgress
                stages={document.stages}
                currentStage={document.currentStage}
                compact={false}
              />
            </div>
          )}

          {/* Error display */}
          {document.error && (
            <div className="mt-2 p-2 bg-[var(--nous-mars)]/10 border border-[var(--nous-mars)]/30 rounded text-xs text-[var(--nous-mars)]">
              {document.error}
            </div>
          )}

          {/* Action buttons */}
          <div className="flex items-center space-x-2 mt-3">
            {document.actions.pause && document.status === 'processing' && (
              <IconButton
                onClick={() => handleAction(() => onPause(document.id))}
                className="h-8 w-8 text-muted-foreground hover:text-[var(--nous-corona)] hover:bg-[var(--nous-corona)]/10 rounded"
                label="Pause"
                icon={<PauseIcon className="h-4 w-4" />}
              />
            )}
            {document.actions.resume && document.status === 'paused' && (
              <IconButton
                onClick={() => handleAction(() => onResume(document.id))}
                className="h-8 w-8 text-muted-foreground hover:text-[var(--nous-terra)] hover:bg-[var(--nous-terra)]/10 rounded"
                label="Resume"
                icon={<PlayIcon className="h-4 w-4" />}
              />
            )}
            {document.actions.retry && document.status === 'failed' && (
              <IconButton
                onClick={() => handleAction(() => onRetry(document.id))}
                className="h-8 w-8 text-muted-foreground hover:text-[var(--nous-sol-safe)] hover:bg-[var(--nous-sol)]/10 rounded"
                label="Retry"
                icon={<ArrowPathIcon className="h-4 w-4" />}
              />
            )}
            {document.actions.cancel &&
              (document.status === 'queued' ||
                document.status === 'processing') && (
                <IconButton
                  onClick={() => handleAction(() => onCancel(document.id))}
                  className="h-8 w-8 text-muted-foreground hover:text-[var(--nous-mars)] hover:bg-[var(--nous-mars)]/10 rounded"
                  label="Cancel"
                  icon={<XMarkIcon className="h-4 w-4" />}
                />
              )}
          </div>
        </div>
      </div>
    </motion.div>
  );
};

// Main Dashboard Component
export const RealtimeStatusDashboard: React.FC<
  RealtimeStatusDashboardProps
> = ({
  className,
  showSystemMetrics = true,
  showFilters = true,
  maxDocuments = 50,
  autoRefresh = true,
}) => {
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('list');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);
  const [selectedFileTypes, setSelectedFileTypes] = useState<string[]>([]);

  const {
    documents,
    systemMetrics,
    isConnected,
    pauseDocument,
    resumeDocument,
    cancelDocument,
    retryDocument,
    pauseSelectedDocuments,
    resumeSelectedDocuments,
    cancelSelectedDocuments,
    retrySelectedDocuments,
    clearNotifications,
    reconnect,
  } = useRealtimeProcessing({ autoConnect: autoRefresh });

  const connectionStatus = useConnectionStatus();
  const store = useRealtimeProcessingStore();

  // Get data from store
  const queue = useRealtimeProcessingStore((state) => state.queue);
  const selectedDocuments = useRealtimeProcessingStore((state) =>
    state.getSelectedDocuments()
  );
  const filteredDocuments = useRealtimeProcessingStore((state) =>
    state.getFilteredDocuments()
  );

  // Apply filters
  const filteredAndSearchedDocs = useMemo(() => {
    let filtered = filteredDocuments;

    // Apply search term
    if (searchTerm) {
      filtered = filtered.filter((doc) =>
        doc.filename.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // Apply status filter
    if (selectedStatuses.length > 0) {
      filtered = filtered.filter((doc) =>
        selectedStatuses.includes(doc.status)
      );
    }

    // Apply file type filter
    if (selectedFileTypes.length > 0) {
      filtered = filtered.filter((doc) =>
        selectedFileTypes.includes(doc.fileType)
      );
    }

    // Limit documents
    return filtered.slice(0, maxDocuments);
  }, [
    filteredDocuments,
    searchTerm,
    selectedStatuses,
    selectedFileTypes,
    maxDocuments,
  ]);

  // Handle document selection
  const handleDocumentSelect = (documentId: string) => {
    store.toggleDocumentSelection(documentId);
  };

  // Handle bulk selection
  const handleSelectAll = () => {
    if (selectedDocuments.length === filteredAndSearchedDocs.length) {
      store.clearDocumentSelection();
    } else {
      store.selectAllDocuments();
      // Then limit to current filtered documents
      const filteredIds = filteredAndSearchedDocs.map((doc) => doc.id);
      store.clearDocumentSelection();
      filteredIds.forEach((id) => store.toggleDocumentSelection(id));
    }
  };

  return (
    <div className={cn('space-y-6', className)}>
      {/* Connection Status Bar */}
      <div
        className={cn(
          'flex items-center justify-between p-3 rounded-lg border',
          isConnected
            ? 'bg-[var(--nous-terra)]/10 border-[var(--nous-terra)]/30'
            : 'bg-[var(--nous-mars)]/10 border-[var(--nous-mars)]/30'
        )}
      >
        <div className="flex items-center space-x-3">
          <SignalIcon
            className={cn(
              'h-5 w-5',
              isConnected
                ? 'text-[var(--nous-terra)]'
                : 'text-[var(--nous-mars)]'
            )}
          />
          <div>
            <span
              className={cn(
                'text-sm font-medium',
                isConnected
                  ? 'text-[var(--nous-terra)]'
                  : 'text-[var(--nous-mars)]'
              )}
            >
              {connectionStatus.status === 'connected'
                ? 'Connected'
                : 'Disconnected'}
            </span>
            {connectionStatus.lastError && (
              <p className="text-xs text-[var(--nous-mars)]">
                {connectionStatus.lastError}
              </p>
            )}
          </div>
        </div>
        {!isConnected && (
          <button
            onClick={reconnect}
            className="px-3 py-1 text-xs font-medium text-[var(--nous-mars)] bg-[var(--nous-mars)]/15 hover:bg-[var(--nous-mars)]/25 rounded"
          >
            Reconnect
          </button>
        )}
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
        <div className="bg-card p-3 rounded-lg border border-border">
          <div className="flex items-center space-x-2">
            <DocumentTextIcon className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-xs text-muted-foreground">Total</p>
              <p className="text-lg font-semibold text-foreground">
                {queue.summary.total}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-card p-3 rounded-lg border border-border">
          <div className="flex items-center space-x-2">
            <ClockIcon className="h-5 w-5 text-[var(--nous-sol-safe)]" />
            <div>
              <p className="text-xs text-muted-foreground">Queued</p>
              <p className="text-lg font-semibold text-[var(--nous-sol-safe)]">
                {queue.summary.queued}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-card p-3 rounded-lg border border-border">
          <div className="flex items-center space-x-2">
            <ArrowPathIcon className="h-5 w-5 text-[var(--nous-sol-safe)]" />
            <div>
              <p className="text-xs text-muted-foreground">Processing</p>
              <p className="text-lg font-semibold text-[var(--nous-sol-safe)]">
                {queue.summary.processing}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-card p-3 rounded-lg border border-border">
          <div className="flex items-center space-x-2">
            <CheckCircleIcon className="h-5 w-5 text-[var(--nous-terra)]" />
            <div>
              <p className="text-xs text-muted-foreground">Completed</p>
              <p className="text-lg font-semibold text-[var(--nous-terra)]">
                {queue.summary.completed}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-card p-3 rounded-lg border border-border">
          <div className="flex items-center space-x-2">
            <XCircleIcon className="h-5 w-5 text-[var(--nous-mars)]" />
            <div>
              <p className="text-xs text-muted-foreground">Failed</p>
              <p className="text-lg font-semibold text-[var(--nous-mars)]">
                {queue.summary.failed}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-card p-3 rounded-lg border border-border">
          <div className="flex items-center space-x-2">
            <PauseIcon className="h-5 w-5 text-[var(--nous-corona)]" />
            <div>
              <p className="text-xs text-muted-foreground">Paused</p>
              <p className="text-lg font-semibold text-[var(--nous-corona)]">
                {queue.summary.paused}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-card p-3 rounded-lg border border-border">
          <div className="flex items-center space-x-2">
            <div className="h-5 w-5 rounded-full bg-[var(--nous-sol)]" />
            <div>
              <p className="text-xs text-muted-foreground">Success Rate</p>
              <p className="text-lg font-semibold text-[var(--nous-sol-safe)]">
                {queue.metrics.successRate.toFixed(1)}%
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Filters and Controls */}
      {showFilters && (
        <div className="bg-card p-4 rounded-lg border border-border">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between space-y-4 lg:space-y-0">
            {/* Search */}
            <div className="flex-1 max-w-md">
              <div className="relative">
                <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search documents..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-border rounded-lg focus:ring-2 focus:ring-[var(--nous-sol)] focus:border-transparent"
                />
              </div>
            </div>

            {/* Filters */}
            <div className="flex items-center space-x-4">
              <select
                multiple
                value={selectedStatuses}
                onChange={(e) =>
                  setSelectedStatuses(
                    Array.from(
                      e.target.selectedOptions,
                      (option) => option.value
                    )
                  )
                }
                className="px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-[var(--nous-sol)] focus:border-transparent"
              >
                <option value="queued">Queued</option>
                <option value="processing">Processing</option>
                <option value="completed">Completed</option>
                <option value="failed">Failed</option>
                <option value="paused">Paused</option>
              </select>

              <select
                multiple
                value={selectedFileTypes}
                onChange={(e) =>
                  setSelectedFileTypes(
                    Array.from(
                      e.target.selectedOptions,
                      (option) => option.value
                    )
                  )
                }
                className="px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-[var(--nous-sol)] focus:border-transparent"
              >
                <option value="pdf">PDF</option>
                <option value="txt">TXT</option>
                <option value="jpg">JPG</option>
                <option value="png">PNG</option>
                <option value="mp3">MP3</option>
                <option value="mp4">MP4</option>
              </select>
            </div>

            {/* View controls */}
            <div className="flex items-center space-x-2">
              <IconButton
                onClick={() => setViewMode('list')}
                className={cn(
                  'h-8 w-8 rounded',
                  viewMode === 'list'
                    ? 'bg-[var(--nous-sol)]/15 text-[var(--nous-sol-safe)]'
                    : 'text-muted-foreground hover:text-foreground'
                )}
                label="List view"
                icon={<ListBulletIcon className="h-5 w-5" />}
              />
              <IconButton
                onClick={() => setViewMode('grid')}
                className={cn(
                  'h-8 w-8 rounded',
                  viewMode === 'grid'
                    ? 'bg-[var(--nous-sol)]/15 text-[var(--nous-sol-safe)]'
                    : 'text-muted-foreground hover:text-foreground'
                )}
                label="Grid view"
                icon={<Squares2X2Icon className="h-5 w-5" />}
              />
            </div>
          </div>

          {/* Bulk actions */}
          {selectedDocuments.length > 0 && (
            <div className="mt-4 flex items-center justify-between p-3 bg-[var(--nous-sol)]/10 rounded-lg">
              <span className="text-sm text-[var(--nous-sol-safe)]">
                {selectedDocuments.length} documents selected
              </span>
              <div className="flex items-center space-x-2">
                <button
                  onClick={pauseSelectedDocuments}
                  className="px-3 py-1 text-xs font-medium text-[var(--nous-corona)] bg-[var(--nous-corona)]/15 hover:bg-[var(--nous-corona)]/25 rounded"
                >
                  Pause All
                </button>
                <button
                  onClick={resumeSelectedDocuments}
                  className="px-3 py-1 text-xs font-medium text-[var(--nous-terra)] bg-[var(--nous-terra)]/15 hover:bg-[var(--nous-terra)]/25 rounded"
                >
                  Resume All
                </button>
                <button
                  onClick={cancelSelectedDocuments}
                  className="px-3 py-1 text-xs font-medium text-[var(--nous-mars)] bg-[var(--nous-mars)]/15 hover:bg-[var(--nous-mars)]/25 rounded"
                >
                  Cancel All
                </button>
                <button
                  onClick={retrySelectedDocuments}
                  className="px-3 py-1 text-xs font-medium text-[var(--nous-sol-safe)] bg-[var(--nous-sol)]/15 hover:bg-[var(--nous-sol)]/25 rounded"
                >
                  Retry All
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Document List */}
      <div className="bg-card rounded-lg border border-border">
        <div className="p-4 border-b border-border">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground">Documents</h2>
            <div className="flex items-center space-x-4">
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={
                    selectedDocuments.length ===
                      filteredAndSearchedDocs.length &&
                    filteredAndSearchedDocs.length > 0
                  }
                  onChange={handleSelectAll}
                  className="h-4 w-4 text-[var(--nous-sol-safe)] focus:ring-[var(--nous-sol)] border-border rounded"
                />
                <span className="text-sm text-foreground">Select All</span>
              </label>
              <span className="text-sm text-muted-foreground">
                {filteredAndSearchedDocs.length} of {queue.summary.total}{' '}
                documents
              </span>
            </div>
          </div>
        </div>

        <div
          className={cn(
            'divide-y divide-[var(--nous-border-1)]',
            viewMode === 'grid' &&
              'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4'
          )}
        >
          <AnimatePresence>
            {filteredAndSearchedDocs.map((document) => (
              <div
                key={document.id}
                className={viewMode === 'list' ? 'p-4' : ''}
              >
                <DocumentCard
                  document={document}
                  selected={selectedDocuments.includes(document.id)}
                  onSelect={handleDocumentSelect}
                  onPause={pauseDocument}
                  onResume={resumeDocument}
                  onCancel={cancelDocument}
                  onRetry={retryDocument}
                  compact={viewMode === 'list'}
                />
              </div>
            ))}
          </AnimatePresence>
        </div>

        {filteredAndSearchedDocs.length === 0 && (
          <div className="p-8 text-center">
            <DocumentTextIcon className="mx-auto h-12 w-12 text-muted-foreground" />
            <p className="mt-2 text-sm text-foreground">No documents found</p>
          </div>
        )}
      </div>

      {/* System Metrics */}
      {showSystemMetrics && (
        <div className="bg-card rounded-lg border border-border p-4">
          <h3 className="text-lg font-semibold text-foreground mb-4">
            System Metrics
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="flex items-center space-x-2">
                <CpuChipIcon className="h-5 w-5 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground">CPU Usage</p>
                  <p className="text-lg font-semibold text-foreground">
                    {systemMetrics.cpuUsage.toFixed(1)}%
                  </p>
                </div>
              </div>
            </div>

            <div>
              <div className="flex items-center space-x-2">
                <CircleStackIcon className="h-5 w-5 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground">Memory Usage</p>
                  <p className="text-lg font-semibold text-foreground">
                    {(systemMetrics.memoryUsage / 1024).toFixed(1)} GB
                  </p>
                </div>
              </div>
            </div>

            <div>
              <div className="flex items-center space-x-2">
                <ServerIcon className="h-5 w-5 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground">Active Jobs</p>
                  <p className="text-lg font-semibold text-foreground">
                    {systemMetrics.activeJobs}
                  </p>
                </div>
              </div>
            </div>

            <div>
              <div className="flex items-center space-x-2">
                <ArrowPathIcon className="h-5 w-5 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground">Avg Duration</p>
                  <p className="text-lg font-semibold text-foreground">
                    {formatDuration(systemMetrics.averageJobDuration)}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RealtimeStatusDashboard;
