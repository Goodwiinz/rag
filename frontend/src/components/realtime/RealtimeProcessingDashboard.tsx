import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ChartBarIcon,
  ClockIcon,
  DocumentIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ArrowPathIcon,
  FunnelIcon,
  XMarkIcon,
  EyeIcon,
  PauseIcon,
  PlayIcon,
  TrashIcon,
  Cog6ToothIcon,
  BellIcon,
  SignalSlashIcon,
  SignalIcon,
  ServerIcon,
  CpuChipIcon,
  CircleStackIcon,
} from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';
import {
  useRealtimeProcessingStore,
  useConnectionStatus,
  useProcessingQueue,
  useSystemMetrics,
  useUIState,
  useNotifications,
} from '@/store/realtimeProcessingStore';
import {
  DocumentProcessingState,
  ProcessingStage,
} from '@/types/realtime-processing';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Progress } from '@/components/ui/progress';
import { toast } from 'react-hot-toast';

interface RealtimeDashboardProps {
  className?: string;
  autoRefresh?: boolean;
  refreshInterval?: number; // seconds
  showControls?: boolean;
  maxHeight?: string;
  enableSounds?: boolean;
  theme?: 'light' | 'dark' | 'auto';
  compactView?: boolean;
}

interface ProcessingStats {
  totalFiles: number;
  completedFiles: number;
  processingFiles: number;
  queuedFiles: number;
  failedFiles: number;
  pausedFiles: number;
  averageProcessingTime: number;
  throughputPerMinute: number;
  successRate: number;
  errorRate: number;
}

export const RealtimeProcessingDashboard: React.FC<RealtimeDashboardProps> = ({
  className,
  autoRefresh = true,
  refreshInterval = 5,
  showControls = true,
  maxHeight = '600px',
  enableSounds = true,
  theme = 'auto',
  compactView = false,
}) => {
  // State
  const [showDetails, setShowDetails] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);

  // Store selectors
  const connection = useConnectionStatus();
  const queue = useProcessingQueue();
  const systemMetrics = useSystemMetrics();
  const ui = useUIState();
  const notifications = useNotifications();

  const {
    updateDocument,
    pauseSelectedDocuments,
    resumeSelectedDocuments,
    cancelSelectedDocuments,
    retrySelectedDocuments,
    selectAllDocuments,
    clearDocumentSelection,
    toggleDocumentSelection,
    toggleSidebar,
    setAutoScroll,
    setCompactView,
    updatePreferences,
  } = useRealtimeProcessingStore();

  // Calculate processing statistics
  const processingStats = useMemo((): ProcessingStats => {
    const { documents, summary, metrics } = queue;

    return {
      totalFiles: summary.total,
      completedFiles: summary.completed,
      processingFiles: summary.processing,
      queuedFiles: summary.queued,
      failedFiles: summary.failed,
      pausedFiles: summary.paused,
      averageProcessingTime: metrics.averageProcessingTime,
      throughputPerMinute: metrics.throughput,
      successRate: metrics.successRate,
      errorRate: metrics.errorRate,
    };
  }, [queue]);

  // Update preferences
  useEffect(() => {
    updatePreferences({
      refreshInterval: refreshInterval * 1000,
      soundEnabled: enableSounds,
      theme,
      compactView,
    });
  }, [refreshInterval, enableSounds, theme, compactView, updatePreferences]);

  // Status helpers
  const getStatusColor = useCallback(
    (status: DocumentProcessingState['status']) => {
      switch (status) {
        case 'completed':
          return 'text-[var(--nous-terra)] bg-[var(--nous-terra)]/10 border-[var(--nous-terra)]/30';
        case 'processing':
          return 'text-[var(--nous-fg-accent-safe)] bg-[var(--nous-sol)]/10 border-[var(--nous-sol)]/30';
        case 'queued':
          return 'text-foreground bg-[var(--nous-bg-2)] border-border';
        case 'uploading':
          return 'text-[var(--nous-corona)] bg-[var(--nous-corona)]/10 border-[var(--nous-corona)]/30';
        case 'paused':
          return 'text-[var(--nous-corona)] bg-[var(--nous-corona)]/10 border-[var(--nous-corona)]/30';
        case 'cancelled':
          return 'text-[var(--nous-fg-3)] bg-[var(--nous-bg-3)] border-[var(--nous-border-1)]';
        case 'failed':
          return 'text-[var(--nous-mars)] bg-[var(--nous-mars)]/10 border-[var(--nous-mars)]/30';
        default:
          return 'text-foreground bg-[var(--nous-bg-2)] border-border';
      }
    },
    []
  );

  const getStatusIcon = useCallback(
    (status: DocumentProcessingState['status']) => {
      const iconClass = 'h-5 w-5';
      switch (status) {
        case 'completed':
          return (
            <CheckCircleIcon
              className={cn(iconClass, 'text-[var(--nous-terra)]')}
            />
          );
        case 'processing':
          return (
            <ArrowPathIcon
              className={cn(
                iconClass,
                'text-[var(--nous-fg-accent-safe)] animate-spin'
              )}
            />
          );
        case 'queued':
          return <ClockIcon className={cn(iconClass, 'text-foreground')} />;
        case 'uploading':
          return (
            <ArrowPathIcon
              className={cn(
                iconClass,
                'text-[var(--nous-corona)] animate-spin'
              )}
            />
          );
        case 'paused':
          return (
            <PauseIcon className={cn(iconClass, 'text-[var(--nous-corona)]')} />
          );
        case 'cancelled':
          return (
            <XMarkIcon className={cn(iconClass, 'text-[var(--nous-fg-3)]')} />
          );
        case 'failed':
          return (
            <ExclamationTriangleIcon
              className={cn(iconClass, 'text-[var(--nous-mars)]')}
            />
          );
        default:
          return <DocumentIcon className={cn(iconClass, 'text-foreground')} />;
      }
    },
    []
  );

  const getFileTypeIcon = useCallback(
    (fileType: DocumentProcessingState['fileType']) => {
      switch (fileType) {
        case 'pdf':
          return <DocumentIcon className="h-5 w-5 text-[var(--nous-mars)]" />;
        case 'txt':
          return (
            <DocumentIcon className="h-5 w-5 text-[var(--nous-fg-accent-safe)]" />
          );
        case 'jpg':
        case 'png':
          return <DocumentIcon className="h-5 w-5 text-[var(--nous-terra)]" />;
        case 'mp3':
          return <DocumentIcon className="h-5 w-5 text-[var(--nous-fg-3)]" />;
        case 'mp4':
          return <DocumentIcon className="h-5 w-5 text-[var(--nous-corona)]" />;
        default:
          return <DocumentIcon className="h-5 w-5 text-foreground" />;
      }
    },
    []
  );

  // Action handlers
  const handlePauseSelected = useCallback(() => {
    pauseSelectedDocuments();
    toast.success('Paused selected documents');
  }, [pauseSelectedDocuments]);

  const handleResumeSelected = useCallback(() => {
    resumeSelectedDocuments();
    toast.success('Resumed selected documents');
  }, [resumeSelectedDocuments]);

  const handleCancelSelected = useCallback(() => {
    if (confirm('Are you sure you want to cancel selected documents?')) {
      cancelSelectedDocuments();
      toast.success('Cancelled selected documents');
    }
  }, [cancelSelectedDocuments]);

  const handleRetrySelected = useCallback(() => {
    retrySelectedDocuments();
    toast.success('Retrying selected documents');
  }, [retrySelectedDocuments]);

  const handleSelectAll = useCallback(() => {
    selectAllDocuments();
  }, [selectAllDocuments]);

  const handleClearSelection = useCallback(() => {
    clearDocumentSelection();
  }, [clearDocumentSelection]);

  const formatFileSize = useCallback((bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  }, []);

  const formatTime = useCallback((seconds: number): string => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600)
      return `${Math.round(seconds / 60)}m ${Math.round(seconds % 60)}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`;
  }, []);

  return (
    <div
      className={cn('space-y-6', className)}
      data-testid="realtime-processing-dashboard"
    >
      {/* Header with Connection Status */}
      <div className="flex items-center justify-between p-4 bg-card border rounded-lg">
        <div className="flex items-center space-x-4">
          <h2 className="text-lg font-semibold text-foreground">
            Document Processing Dashboard
          </h2>

          {/* Connection Status */}
          <div className="flex items-center space-x-2">
            {connection.status === 'connected' ? (
              <>
                <SignalIcon className="h-4 w-4 text-[var(--nous-terra)]" />
                <span className="text-sm text-[var(--nous-terra)]">
                  Connected
                </span>
              </>
            ) : (
              <>
                <SignalSlashIcon className="h-4 w-4 text-[var(--nous-mars)]" />
                <span className="text-sm text-[var(--nous-mars)]">
                  {connection.status === 'connecting'
                    ? 'Connecting...'
                    : 'Disconnected'}
                </span>
              </>
            )}
            {connection.latency > 0 && (
              <span className="text-xs text-muted-foreground">
                {connection.latency}ms
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {/* Notifications */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowNotifications(true)}
            className="relative"
          >
            <BellIcon className="h-4 w-4" />
            {notifications.length > 0 && (
              <span className="absolute -top-1 -right-1 h-4 w-4 bg-[var(--nous-mars)] text-white text-xs rounded-full flex items-center justify-center">
                {notifications.length}
              </span>
            )}
          </Button>

          {/* Settings */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowSettings(true)}
          >
            <Cog6ToothIcon className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Header Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 bg-card border rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Total Files</p>
              <p className="text-2xl font-bold text-foreground">
                {processingStats.totalFiles}
              </p>
            </div>
            <DocumentIcon className="h-8 w-8 text-muted-foreground" />
          </div>
        </div>

        <div className="p-4 bg-card border rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Processing</p>
              <p className="text-2xl font-bold text-[var(--nous-fg-accent-safe)]">
                {processingStats.processingFiles}
              </p>
            </div>
            <ArrowPathIcon className="h-8 w-8 text-[var(--nous-fg-accent-safe)] animate-spin" />
          </div>
        </div>

        <div className="p-4 bg-card border rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Completed</p>
              <p className="text-2xl font-bold text-[var(--nous-terra)]">
                {processingStats.completedFiles}
              </p>
            </div>
            <CheckCircleIcon className="h-8 w-8 text-[var(--nous-terra)]" />
          </div>
        </div>

        <div className="p-4 bg-card border rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Failed</p>
              <p className="text-2xl font-bold text-[var(--nous-mars)]">
                {processingStats.failedFiles}
              </p>
            </div>
            <ExclamationTriangleIcon className="h-8 w-8 text-[var(--nous-mars)]" />
          </div>
        </div>
      </div>

      {/* Performance Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 bg-card border rounded-lg">
          <div className="flex items-center space-x-2">
            <ClockIcon className="h-5 w-5 text-muted-foreground" />
            <h3 className="text-sm font-medium text-muted-foreground">
              Average Processing Time
            </h3>
          </div>
          <p className="text-lg font-semibold text-foreground mt-1">
            {formatTime(processingStats.averageProcessingTime)}
          </p>
        </div>

        <div className="p-4 bg-card border rounded-lg">
          <div className="flex items-center space-x-2">
            <ChartBarIcon className="h-5 w-5 text-muted-foreground" />
            <h3 className="text-sm font-medium text-muted-foreground">
              Throughput
            </h3>
          </div>
          <p className="text-lg font-semibold text-foreground mt-1">
            {processingStats.throughputPerMinute.toFixed(1)} files/min
          </p>
        </div>

        <div className="p-4 bg-card border rounded-lg">
          <div className="flex items-center space-x-2">
            <ServerIcon className="h-5 w-5 text-muted-foreground" />
            <h3 className="text-sm font-medium text-muted-foreground">
              Success Rate
            </h3>
          </div>
          <p className="text-lg font-semibold text-foreground mt-1">
            {processingStats.successRate.toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Controls */}
      {showControls && queue.documents.length > 0 && (
        <div className="flex items-center justify-between p-4 bg-card border rounded-lg">
          <div className="flex items-center space-x-4">
            {/* Selection Controls */}
            {ui.selectedDocuments.length > 0 && (
              <>
                <span className="text-sm text-muted-foreground">
                  {ui.selectedDocuments.length} selected
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleClearSelection}
                >
                  Clear Selection
                </Button>
              </>
            )}

            {ui.selectedDocuments.length === 0 && (
              <Button variant="outline" size="sm" onClick={handleSelectAll}>
                Select All
              </Button>
            )}

            {/* Bulk Actions */}
            {ui.selectedDocuments.length > 0 && (
              <div className="flex items-center space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handlePauseSelected}
                  disabled={ui.selectedDocuments.length === 0}
                >
                  <PauseIcon className="h-4 w-4 mr-2" />
                  Pause
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleResumeSelected}
                  disabled={ui.selectedDocuments.length === 0}
                >
                  <PlayIcon className="h-4 w-4 mr-2" />
                  Resume
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRetrySelected}
                  disabled={ui.selectedDocuments.length === 0}
                >
                  <ArrowPathIcon className="h-4 w-4 mr-2" />
                  Retry
                </Button>

                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleCancelSelected}
                  disabled={ui.selectedDocuments.length === 0}
                >
                  <XMarkIcon className="h-4 w-4 mr-2" />
                  Cancel
                </Button>
              </div>
            )}
          </div>

          <div className="flex items-center space-x-2">
            {/* Compact View Toggle */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCompactView(!compactView)}
            >
              {compactView ? 'Expanded View' : 'Compact View'}
            </Button>
          </div>
        </div>
      )}

      {/* Processing Queue */}
      <div className="bg-card border rounded-lg overflow-hidden">
        <div className="p-4 border-b">
          <h3 className="text-lg font-semibold text-foreground">
            Processing Queue ({queue.documents.length} files)
          </h3>
        </div>

        <ScrollArea className={cn('h-[600px]')} style={{ maxHeight }}>
          {queue.documents.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              <DocumentIcon className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No files in processing queue</p>
              <p className="text-sm mt-2">Upload documents to see them here</p>
            </div>
          ) : (
            <div className="divide-y">
              {queue.documents.map((document) => (
                <DocumentCard
                  key={document.id}
                  document={document}
                  isSelected={ui.selectedDocuments.includes(document.id)}
                  onSelect={() => toggleDocumentSelection(document.id)}
                  onShowDetails={() => setShowDetails(document.id)}
                  getStatusColor={getStatusColor}
                  getStatusIcon={getStatusIcon}
                  getFileTypeIcon={getFileTypeIcon}
                  formatFileSize={formatFileSize}
                  formatTime={formatTime}
                  compact={compactView}
                />
              ))}
            </div>
          )}
        </ScrollArea>
      </div>

      {/* Document Details Modal */}
      {showDetails && (
        <Dialog open={!!showDetails} onOpenChange={() => setShowDetails(null)}>
          <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden">
            <DialogHeader>
              <DialogTitle>Processing Details</DialogTitle>
            </DialogHeader>
            <div className="mt-4">
              {(() => {
                const document = queue.documents.find(
                  (d) => d.id === showDetails
                );
                return document ? (
                  <DocumentDetails document={document} />
                ) : null;
              })()}
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* Settings Modal */}
      {showSettings && (
        <Dialog open={showSettings} onOpenChange={setShowSettings}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Dashboard Settings</DialogTitle>
            </DialogHeader>
            <SettingsPanel onClose={() => setShowSettings(false)} />
          </DialogContent>
        </Dialog>
      )}

      {/* Notifications Modal */}
      {showNotifications && (
        <Dialog open={showNotifications} onOpenChange={setShowNotifications}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Notifications</DialogTitle>
            </DialogHeader>
            <NotificationsPanel />
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};

// Document Card Component
interface DocumentCardProps {
  document: DocumentProcessingState;
  isSelected: boolean;
  onSelect: () => void;
  onShowDetails: () => void;
  getStatusColor: (status: DocumentProcessingState['status']) => string;
  getStatusIcon: (status: DocumentProcessingState['status']) => React.ReactNode;
  getFileTypeIcon: (
    fileType: DocumentProcessingState['fileType']
  ) => React.ReactNode;
  formatFileSize: (bytes: number) => string;
  formatTime: (seconds: number) => string;
  compact?: boolean;
}

const DocumentCard: React.FC<DocumentCardProps> = ({
  document,
  isSelected,
  onSelect,
  onShowDetails,
  getStatusColor,
  getStatusIcon,
  getFileTypeIcon,
  formatFileSize,
  formatTime,
  compact = false,
}) => {
  const getElapsedTime = (): string => {
    if (!document.metadata.uploadStartedAt) return 'N/A';

    const startTime = new Date(document.metadata.uploadStartedAt).getTime();
    const endTime = document.metadata.completedAt
      ? new Date(document.metadata.completedAt).getTime()
      : Date.now();
    const elapsedSeconds = (endTime - startTime) / 1000;

    return formatTime(elapsedSeconds);
  };

  return (
    <div
      className={cn(
        'p-4 hover:bg-accent/50 transition-colors cursor-pointer',
        isSelected && 'bg-accent/50 ring-1 ring-inset ring-primary/40',
        compact && 'p-3'
      )}
      onClick={onSelect}
      role="article"
      aria-label={`Document ${document.filename}, status: ${document.status}, progress: ${document.overallProgress}%`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-3 flex-1 min-w-0">
          {/* Checkbox for selection */}
          <input
            type="checkbox"
            checked={isSelected}
            onChange={onSelect}
            className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
            onClick={(e) => e.stopPropagation()}
            aria-label={`Select ${document.filename}`}
          />

          {/* File type icon */}
          <div className="text-xl flex-shrink-0">
            {getFileTypeIcon(document.fileType)}
          </div>

          {/* Document info */}
          <div className="flex-1 min-w-0">
            <p
              className={cn(
                'text-sm font-medium text-foreground truncate',
                compact && 'text-xs'
              )}
            >
              {document.filename}
            </p>
            <div className="flex items-center space-x-2 mt-1">
              <span className="text-xs text-muted-foreground">
                {formatFileSize(document.metadata.fileSize)}
              </span>
              {!compact && (
                <>
                  <span className="text-xs text-muted-foreground">•</span>
                  <span className="text-xs text-muted-foreground">
                    {getElapsedTime()}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2 flex-shrink-0">
          {/* Status badge */}
          <Badge
            className={cn('text-xs', getStatusColor(document.status))}
            variant="outline"
          >
            <div className="flex items-center space-x-1">
              {getStatusIcon(document.status)}
              <span className="capitalize">
                {document.status.replace('_', ' ')}
              </span>
            </div>
          </Badge>

          {/* Actions */}
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              onShowDetails();
            }}
            aria-label={`View details for ${document.filename}`}
          >
            <EyeIcon className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Progress bar */}
      {document.status !== 'completed' &&
        document.status !== 'failed' &&
        document.status !== 'cancelled' && (
          <div className="mt-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-muted-foreground">
                {document.currentStage.name} - {document.overallProgress}%
                complete
              </span>
              {document.metadata.estimatedTimeRemaining && (
                <span className="text-xs text-muted-foreground">
                  ~{formatTime(document.metadata.estimatedTimeRemaining)}{' '}
                  remaining
                </span>
              )}
            </div>
            <Progress value={document.overallProgress} className="h-2" />

            {/* Stage progress */}
            {!compact && document.stages.length > 1 && (
              <div className="mt-2">
                <StageIndicator
                  stages={document.stages}
                  currentStage={document.currentStage}
                  compact={true}
                />
              </div>
            )}
          </div>
        )}

      {/* Error message */}
      {document.error && (
        <div className="mt-2 p-2 bg-destructive/10 border border-destructive/20 rounded text-xs text-destructive">
          {document.error}
        </div>
      )}
    </div>
  );
};

// Stage Indicator Component
interface StageIndicatorProps {
  stages: ProcessingStage[];
  currentStage: ProcessingStage;
  compact?: boolean;
}

const StageIndicator: React.FC<StageIndicatorProps> = ({
  stages,
  currentStage,
  compact = false,
}) => {
  const getStageStatus = (stage: ProcessingStage) => {
    if (stage.status === 'completed') return 'completed';
    if (stage.status === 'failed') return 'error';
    if (stage.status === 'in_progress') return 'processing';
    if (stage.id === currentStage.id) return 'processing';
    return 'pending';
  };

  const getStageIcon = (stage: ProcessingStage) => {
    switch (stage.status) {
      case 'completed':
        return <CheckCircleIcon className="h-3 w-3 text-[var(--nous-terra)]" />;
      case 'failed':
        return (
          <ExclamationTriangleIcon className="h-3 w-3 text-[var(--nous-mars)]" />
        );
      case 'in_progress':
        return (
          <ArrowPathIcon className="h-3 w-3 text-[var(--nous-fg-accent-safe)] animate-spin" />
        );
      default:
        return <div className="h-3 w-3 rounded-full bg-[var(--nous-bg-3)]" />;
    }
  };

  if (compact) {
    return (
      <div className="flex items-center space-x-1">
        {stages.map((stage, index) => (
          <div key={stage.id} className="flex items-center space-x-1">
            {getStageIcon(stage)}
            {index < stages.length - 1 && (
              <div
                className={cn(
                  'h-0.5 w-4',
                  stage.status === 'completed'
                    ? 'bg-[var(--nous-terra)]'
                    : 'bg-[var(--nous-bg-3)]'
                )}
              />
            )}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
      {stages.map((stage) => (
        <div
          key={stage.id}
          className={cn(
            'p-2 rounded border text-xs',
            getStageStatus(stage) === 'completed' &&
              'bg-[var(--nous-terra)]/10 border-[var(--nous-terra)]/30',
            getStageStatus(stage) === 'processing' &&
              'bg-[var(--nous-sol)]/10 border-[var(--nous-sol)]/30',
            getStageStatus(stage) === 'error' &&
              'bg-[var(--nous-mars)]/10 border-[var(--nous-mars)]/30',
            getStageStatus(stage) === 'pending' &&
              'bg-[var(--nous-bg-2)] border-border'
          )}
        >
          <div className="flex items-center space-x-2 mb-1">
            {getStageIcon(stage)}
            <span className="font-medium truncate">{stage.name}</span>
          </div>
          {stage.status === 'in_progress' && (
            <div className="w-full bg-[var(--nous-bg-3)] rounded-full h-1">
              <div
                className="bg-[var(--nous-sol)] h-1 rounded-full transition-all duration-300"
                style={{ width: `${stage.progress}%` }}
              />
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

// Document Details Component
interface DocumentDetailsProps {
  document: DocumentProcessingState;
}

const DocumentDetails: React.FC<DocumentDetailsProps> = ({ document }) => {
  const formatTimestamp = (timestamp: string): string => {
    return new Date(timestamp).toLocaleString();
  };

  return (
    <ScrollArea className="h-[60vh]">
      <div className="space-y-6">
        {/* Basic Information */}
        <div>
          <h3 className="text-lg font-semibold mb-3">Basic Information</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-muted-foreground">
                File Name
              </label>
              <p className="text-sm text-foreground">{document.filename}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">
                File Type
              </label>
              <p className="text-sm text-foreground uppercase">
                {document.fileType}
              </p>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">
                File Size
              </label>
              <p className="text-sm text-foreground">
                {(document.metadata.fileSize / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">
                Status
              </label>
              <p className="text-sm text-foreground capitalize">
                {document.status.replace('_', ' ')}
              </p>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">
                Progress
              </label>
              <p className="text-sm text-foreground">
                {document.overallProgress}%
              </p>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">
                Retry Count
              </label>
              <p className="text-sm text-foreground">{document.retryCount}</p>
            </div>
          </div>
        </div>

        {/* Processing Stages */}
        <div>
          <h3 className="text-lg font-semibold mb-3">Processing Stages</h3>
          <div className="space-y-3">
            {document.stages.map((stage, index) => (
              <div key={stage.id} className="p-3 border rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-medium">{stage.name}</span>
                    {stage.status === 'completed' && (
                      <CheckCircleIcon className="h-4 w-4 text-[var(--nous-terra)]" />
                    )}
                    {stage.status === 'failed' && (
                      <ExclamationTriangleIcon className="h-4 w-4 text-[var(--nous-mars)]" />
                    )}
                    {stage.status === 'in_progress' && (
                      <ArrowPathIcon className="h-4 w-4 text-[var(--nous-fg-accent-safe)] animate-spin" />
                    )}
                  </div>
                  <span className="text-sm text-muted-foreground">
                    {stage.progress}%
                  </span>
                </div>

                <p className="text-xs text-muted-foreground mb-2">
                  {stage.description}
                </p>

                {stage.status === 'in_progress' && (
                  <Progress value={stage.progress} className="h-2 mb-2" />
                )}

                {stage.error && (
                  <div className="p-2 bg-[var(--nous-mars)]/10 border border-[var(--nous-mars)]/30 rounded text-xs text-[var(--nous-mars)]">
                    {stage.error}
                  </div>
                )}

                <div className="flex items-center space-x-4 mt-2 text-xs text-muted-foreground">
                  {stage.startedAt && (
                    <span>Started: {formatTimestamp(stage.startedAt)}</span>
                  )}
                  {stage.completedAt && (
                    <span>Completed: {formatTimestamp(stage.completedAt)}</span>
                  )}
                  {stage.duration && (
                    <span>Duration: {(stage.duration / 1000).toFixed(2)}s</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Timeline */}
        <div>
          <h3 className="text-lg font-semibold mb-3">Timeline</h3>
          <div className="space-y-2">
            <div className="flex items-center space-x-3 text-sm">
              <div className="w-3 h-3 rounded-full bg-[var(--nous-sol)]" />
              <span>
                Upload Started:{' '}
                {formatTimestamp(document.metadata.uploadStartedAt)}
              </span>
            </div>
            {document.metadata.processingStartedAt && (
              <div className="flex items-center space-x-3 text-sm">
                <div className="w-3 h-3 rounded-full bg-[var(--nous-corona)]" />
                <span>
                  Processing Started:{' '}
                  {formatTimestamp(document.metadata.processingStartedAt)}
                </span>
              </div>
            )}
            {document.metadata.completedAt && (
              <div className="flex items-center space-x-3 text-sm">
                <div className="w-3 h-3 rounded-full bg-[var(--nous-terra)]" />
                <span>
                  Completed: {formatTimestamp(document.metadata.completedAt)}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Error Details */}
        {document.error && (
          <div>
            <h3 className="text-lg font-semibold mb-3">Error Details</h3>
            <div className="p-3 bg-[var(--nous-mars)]/10 border border-[var(--nous-mars)]/30 rounded text-sm text-[var(--nous-mars)]">
              {document.error}
            </div>
          </div>
        )}
      </div>
    </ScrollArea>
  );
};

// Settings Panel Component
interface SettingsPanelProps {
  onClose: () => void;
}

const SettingsPanel: React.FC<SettingsPanelProps> = ({ onClose }) => {
  const {
    preferences,
    ui,
    updatePreferences,
    setAutoScroll,
    toggleSidebar,
    setTheme,
  } = useRealtimeProcessingStore();

  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm font-medium text-muted-foreground">
          Theme
        </label>
        <select
          value={ui.theme}
          onChange={(e) => setTheme(e.target.value as any)}
          className="w-full mt-1 p-2 border rounded"
        >
          <option value="light">Light</option>
          <option value="dark">Dark</option>
          <option value="auto">Auto</option>
        </select>
      </div>

      <div>
        <label className="text-sm font-medium text-muted-foreground">
          Refresh Interval
        </label>
        <select
          value={preferences.refreshInterval}
          onChange={(e) =>
            updatePreferences({ refreshInterval: parseInt(e.target.value) })
          }
          className="w-full mt-1 p-2 border rounded"
        >
          <option value={500}>500ms</option>
          <option value={1000}>1s</option>
          <option value={2000}>2s</option>
          <option value={5000}>5s</option>
        </select>
      </div>

      <div>
        <label className="text-sm font-medium text-muted-foreground">
          Max Notifications
        </label>
        <select
          value={preferences.maxNotifications}
          onChange={(e) =>
            updatePreferences({ maxNotifications: parseInt(e.target.value) })
          }
          className="w-full mt-1 p-2 border rounded"
        >
          <option value={5}>5</option>
          <option value={10}>10</option>
          <option value={20}>20</option>
          <option value={50}>50</option>
        </select>
      </div>

      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-muted-foreground">
          Sound Notifications
        </label>
        <input
          type="checkbox"
          checked={preferences.soundEnabled}
          onChange={(e) =>
            updatePreferences({ soundEnabled: e.target.checked })
          }
          className="rounded"
        />
      </div>

      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-muted-foreground">
          Desktop Notifications
        </label>
        <input
          type="checkbox"
          checked={preferences.desktopNotifications}
          onChange={(e) =>
            updatePreferences({ desktopNotifications: e.target.checked })
          }
          className="rounded"
        />
      </div>

      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-muted-foreground">
          Auto-scroll
        </label>
        <input
          type="checkbox"
          checked={ui.autoScrollEnabled}
          onChange={(e) => setAutoScroll(e.target.checked)}
          className="rounded"
        />
      </div>

      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-muted-foreground">
          Compact View
        </label>
        <input
          type="checkbox"
          checked={ui.compactView}
          onChange={(e) => setCompactView(e.target.checked)}
          className="rounded"
        />
      </div>

      <div className="flex justify-end space-x-2 pt-4">
        <Button variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={onClose}>Save Settings</Button>
      </div>
    </div>
  );
};

// Notifications Panel Component
const NotificationsPanel: React.FC = () => {
  const { notifications, clearNotifications, removeNotification } =
    useRealtimeProcessingStore();

  if (notifications.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <BellIcon className="h-8 w-8 mx-auto mb-2 opacity-50" />
        <p>No notifications</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between pb-2 border-b">
        <h4 className="font-medium">Notifications ({notifications.length})</h4>
        <Button variant="outline" size="sm" onClick={clearNotifications}>
          Clear All
        </Button>
      </div>

      <div className="space-y-2 max-h-96 overflow-y-auto">
        {notifications.map((notification) => (
          <div
            key={notification.id}
            className={cn(
              'p-3 rounded-lg border',
              notification.type === 'success' &&
                'bg-[var(--nous-terra)]/10 border-[var(--nous-terra)]/30',
              notification.type === 'error' &&
                'bg-[var(--nous-mars)]/10 border-[var(--nous-mars)]/30',
              notification.type === 'warning' &&
                'bg-[var(--nous-corona)]/10 border-[var(--nous-corona)]/30',
              notification.type === 'info' &&
                'bg-[var(--nous-sol)]/10 border-[var(--nous-sol)]/30'
            )}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h5 className="font-medium text-sm">{notification.title}</h5>
                <p className="text-xs text-muted-foreground mt-1">
                  {notification.message}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {new Date(notification.timestamp).toLocaleTimeString()}
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => removeNotification(notification.id)}
                className="ml-2"
              >
                <XMarkIcon className="h-3 w-3" />
              </Button>
            </div>

            {notification.actions && notification.actions.length > 0 && (
              <div className="flex space-x-2 mt-2">
                {notification.actions.map((action, index) => (
                  <Button
                    key={index}
                    variant="outline"
                    size="sm"
                    onClick={action.action}
                    className="text-xs"
                  >
                    {action.label}
                  </Button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default RealtimeProcessingDashboard;
