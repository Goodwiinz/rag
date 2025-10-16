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
} from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';
import { useDocumentUpload } from '@/hooks/upload/useDocumentUpload';
import { useDocumentProcessingUpdates } from '@/hooks/useWebSocket';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { UploadQueueItem } from '@/services/uploadService';

interface ProcessingDashboardProps {
  className?: string;
  autoRefresh?: boolean;
  refreshInterval?: number; // seconds
  showControls?: boolean;
  maxHeight?: string;
}

interface ProcessingStats {
  totalFiles: number;
  completedFiles: number;
  processingFiles: number;
  queuedFiles: number;
  failedFiles: number;
  averageProcessingTime: number;
  throughputPerHour: number;
  errorRate: number;
}

interface TimeSeriesData {
  timestamp: number;
  completed: number;
  failed: number;
  processing: number;
}

export const ProcessingDashboard: React.FC<ProcessingDashboardProps> = ({
  className,
  autoRefresh = true,
  refreshInterval = 5,
  showControls = true,
  maxHeight = '600px',
}) => {
  const [isPaused, setIsPaused] = useState(false);
  const [showDetails, setShowDetails] = useState<string | null>(null);
  const [selectedFilter, setSelectedFilter] = useState<'all' | 'processing' | 'completed' | 'failed' | 'queued'>('all');
  const [timeSeriesData, setTimeSeriesData] = useState<TimeSeriesData[]>([]);
  const [showChart, setShowChart] = useState(false);

  const {
    queueItems,
    stats,
    isUploading,
    hasActiveUploads,
    retryUpload,
    cancelAllUploads,
    cleanupCompleted,
    formatFileSize,
    formatTime,
    getStatusText,
    getFileIcon,
  } = useDocumentUpload();

  const { updates: processingUpdates } = useDocumentProcessingUpdates();

  // Calculate processing statistics
  const processingStats = useMemo((): ProcessingStats => {
    const totalFiles = queueItems.length;
    const completedFiles = queueItems.filter(item => item.status === 'completed').length;
    const processingFiles = queueItems.filter(item => item.status === 'processing').length;
    const queuedFiles = queueItems.filter(item => item.status === 'pending').length;
    const failedFiles = queueItems.filter(item => item.status === 'error').length;

    // Calculate average processing time
    const completedItems = queueItems.filter(item =>
      item.status === 'completed' && item.uploadStartTime && item.completedAt
    );
    const averageProcessingTime = completedItems.length > 0
      ? completedItems.reduce((sum, item) => {
          const totalTime = (item.completedAt! - item.uploadStartTime!) / 1000;
          return sum + totalTime;
        }, 0) / completedItems.length
      : 0;

    // Calculate throughput per hour (last hour)
    const oneHourAgo = Date.now() - (60 * 60 * 1000);
    const recentCompleted = queueItems.filter(item =>
      item.status === 'completed' &&
      item.completedAt &&
      item.completedAt > oneHourAgo
    );
    const throughputPerHour = recentCompleted.length;

    // Calculate error rate
    const errorRate = totalFiles > 0 ? (failedFiles / totalFiles) * 100 : 0;

    return {
      totalFiles,
      completedFiles,
      processingFiles,
      queuedFiles,
      failedFiles,
      averageProcessingTime,
      throughputPerHour,
      errorRate,
    };
  }, [queueItems]);

  // Filter queue items based on selected filter
  const filteredItems = useMemo(() => {
    switch (selectedFilter) {
      case 'processing':
        return queueItems.filter(item => item.status === 'processing');
      case 'completed':
        return queueItems.filter(item => item.status === 'completed');
      case 'failed':
        return queueItems.filter(item => item.status === 'error');
      case 'queued':
        return queueItems.filter(item => item.status === 'pending');
      default:
        return queueItems;
    }
  }, [queueItems, selectedFilter]);

  // Update time series data
  useEffect(() => {
    if (!isPaused && autoRefresh) {
      const interval = setInterval(() => {
        const now = Date.now();
        const dataPoint: TimeSeriesData = {
          timestamp: now,
          completed: processingStats.completedFiles,
          failed: processingStats.failedFiles,
          processing: processingStats.processingFiles,
        };

        setTimeSeriesData(prev => {
          const updated = [...prev, dataPoint];
          // Keep only last 20 data points
          return updated.slice(-20);
        });
      }, refreshInterval * 1000);

      return () => clearInterval(interval);
    }
    return undefined;
  }, [isPaused, autoRefresh, refreshInterval, processingStats]);

  // Handle WebSocket updates
  useEffect(() => {
    processingUpdates.forEach((update) => {
      // Real-time updates are handled by the useDocumentUpload hook
      // This effect can be used for additional real-time features
    });
  }, [processingUpdates]);

  const handleRetry = useCallback((fileId: string) => {
    retryUpload(fileId);
  }, [retryUpload]);

  const handleCancelAll = useCallback(() => {
    if (confirm('Are you sure you want to cancel all uploads?')) {
      cancelAllUploads();
    }
  }, [cancelAllUploads]);

  const handleCleanup = useCallback(() => {
    const removedCount = cleanupCompleted();
    if (removedCount > 0) {
      // Show success message or notification
      console.log(`Cleaned up ${removedCount} completed items`);
    }
  }, [cleanupCompleted]);

  const getStatusColor = useCallback((status: UploadQueueItem['status']) => {
    switch (status) {
      case 'completed':
        return 'text-green-600 bg-green-50';
      case 'processing':
        return 'text-blue-600 bg-blue-50';
      case 'pending':
        return 'text-gray-600 bg-gray-50';
      case 'error':
        return 'text-red-600 bg-red-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  }, []);

  const getStatusIcon = useCallback((status: UploadQueueItem['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="h-5 w-5" />;
      case 'processing':
        return <ArrowPathIcon className="h-5 w-5 animate-spin" />;
      case 'pending':
        return <ClockIcon className="h-5 w-5" />;
      case 'error':
        return <ExclamationTriangleIcon className="h-5 w-5" />;
      default:
        return <DocumentIcon className="h-5 w-5" />;
    }
  }, []);

  return (
    <div className={cn("space-y-6", className)}>
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
              <p className="text-2xl font-bold text-blue-600">
                {processingStats.processingFiles}
              </p>
            </div>
            <ArrowPathIcon className="h-8 w-8 text-blue-600 animate-spin" />
          </div>
        </div>

        <div className="p-4 bg-card border rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Completed</p>
              <p className="text-2xl font-bold text-green-600">
                {processingStats.completedFiles}
              </p>
            </div>
            <CheckCircleIcon className="h-8 w-8 text-green-600" />
          </div>
        </div>

        <div className="p-4 bg-card border rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Failed</p>
              <p className="text-2xl font-bold text-red-600">
                {processingStats.failedFiles}
              </p>
            </div>
            <ExclamationTriangleIcon className="h-8 w-8 text-red-600" />
          </div>
        </div>
      </div>

      {/* Performance Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 bg-card border rounded-lg">
          <h3 className="text-sm font-medium text-muted-foreground mb-2">
            Average Processing Time
          </h3>
          <p className="text-lg font-semibold text-foreground">
            {formatTime(processingStats.averageProcessingTime)}
          </p>
        </div>

        <div className="p-4 bg-card border rounded-lg">
          <h3 className="text-sm font-medium text-muted-foreground mb-2">
            Throughput (Last Hour)
          </h3>
          <p className="text-lg font-semibold text-foreground">
            {processingStats.throughputPerHour} files/hour
          </p>
        </div>

        <div className="p-4 bg-card border rounded-lg">
          <h3 className="text-sm font-medium text-muted-foreground mb-2">
            Error Rate
          </h3>
          <p className="text-lg font-semibold text-foreground">
            {processingStats.errorRate.toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Controls */}
      {showControls && (
        <div className="flex items-center justify-between p-4 bg-card border rounded-lg">
          <div className="flex items-center space-x-4">
            {/* Filter */}
            <div className="flex items-center space-x-2">
              <FunnelIcon className="h-4 w-4 text-muted-foreground" />
              <select
                value={selectedFilter}
                onChange={(e) => setSelectedFilter(e.target.value as any)}
                className="text-sm border rounded px-2 py-1"
              >
                <option value="all">All Files</option>
                <option value="queued">Queued</option>
                <option value="processing">Processing</option>
                <option value="completed">Completed</option>
                <option value="failed">Failed</option>
              </select>
            </div>

            {/* Pause/Resume */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsPaused(!isPaused)}
            >
              {isPaused ? (
                <>
                  <PlayIcon className="h-4 w-4 mr-2" />
                  Resume
                </>
              ) : (
                <>
                  <PauseIcon className="h-4 w-4 mr-2" />
                  Pause
                </>
              )}
            </Button>

            {/* Show Chart */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowChart(!showChart)}
            >
              <ChartBarIcon className="h-4 w-4 mr-2" />
              Chart
            </Button>
          </div>

          <div className="flex items-center space-x-2">
            {/* Cleanup */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleCleanup}
            >
              <TrashIcon className="h-4 w-4 mr-2" />
              Cleanup
            </Button>

            {/* Cancel All */}
            {hasActiveUploads && (
              <Button
                variant="destructive"
                size="sm"
                onClick={handleCancelAll}
              >
                <XMarkIcon className="h-4 w-4 mr-2" />
                Cancel All
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Processing Queue */}
      <div className="bg-card border rounded-lg overflow-hidden">
        <div className="p-4 border-b">
          <h3 className="text-lg font-semibold text-foreground">
            Processing Queue ({filteredItems.length} files)
          </h3>
        </div>

        <div
          className="overflow-y-auto"
          style={{ maxHeight }}
        >
          {filteredItems.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              <DocumentIcon className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No files in queue</p>
            </div>
          ) : (
            <div className="divide-y">
              {filteredItems.map((item) => (
                <ProcessingQueueItem
                  key={item.id}
                  item={item}
                  onRetry={handleRetry}
                  onShowDetails={() => setShowDetails(item.id)}
                  getStatusColor={getStatusColor}
                  getStatusIcon={getStatusIcon}
                  getFileIcon={getFileIcon}
                  formatFileSize={formatFileSize}
                  formatTime={formatTime}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Time Series Chart Dialog */}
      {showChart && (
        <Dialog open={showChart} onOpenChange={setShowChart}>
          <DialogContent className="max-w-4xl">
            <DialogHeader>
              <DialogTitle>Processing Activity</DialogTitle>
            </DialogHeader>
            <ProcessingChart data={timeSeriesData} />
          </DialogContent>
        </Dialog>
      )}

      {/* Item Details Dialog */}
      {showDetails && (
        <Dialog open={!!showDetails} onOpenChange={() => setShowDetails(null)}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Processing Details</DialogTitle>
            </DialogHeader>
            {(() => {
              const item = queueItems.find(i => i.id === showDetails);
              return item ? <ProcessingItemDetails item={item} /> : null;
            })()}
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};

// Processing Queue Item Component
interface ProcessingQueueItemProps {
  item: UploadQueueItem;
  onRetry: (fileId: string) => void;
  onShowDetails: () => void;
  getStatusColor: (status: UploadQueueItem['status']) => string;
  getStatusIcon: (status: UploadQueueItem['status']) => React.ReactNode;
  getFileIcon: (file: File) => string;
  formatFileSize: (bytes: number) => string;
  formatTime: (seconds: number) => string;
}

const ProcessingQueueItem: React.FC<ProcessingQueueItemProps> = ({
  item,
  onRetry,
  onShowDetails,
  getStatusColor,
  getStatusIcon,
  getFileIcon,
  formatFileSize,
  formatTime,
}) => {
  const getStatusText = (status: UploadQueueItem['status']): string => {
    switch (status) {
      case 'pending':
        return 'Queued';
      case 'uploading':
        return 'Uploading';
      case 'processing':
        return 'Processing';
      case 'completed':
        return 'Completed';
      case 'error':
        return 'Failed';
      default:
        return 'Unknown';
    }
  };

  const getElapsedTime = (): string => {
    if (!item.uploadStartTime) return 'N/A';

    const startTime = item.uploadStartTime;
    const endTime = item.completedAt || Date.now();
    const elapsedSeconds = (endTime - startTime) / 1000;

    return formatTime(elapsedSeconds);
  };

  return (
    <div className="p-4 hover:bg-accent/50 transition-colors">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-3 flex-1 min-w-0">
          <div className="text-xl">
            {getFileIcon(item.file)}
          </div>

          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground truncate">
              {item.file.name}
            </p>
            <div className="flex items-center space-x-2 mt-1">
              <span className="text-xs text-muted-foreground">
                {formatFileSize(item.file.size)}
              </span>
              <span className="text-xs text-muted-foreground">•</span>
              <span className="text-xs text-muted-foreground">
                {getElapsedTime()}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <Badge
            className={cn("text-xs", getStatusColor(item.status))}
          >
            <div className="flex items-center space-x-1">
              {getStatusIcon(item.status)}
              <span>{getStatusText(item.status)}</span>
            </div>
          </Badge>

          <Button
            variant="ghost"
            size="sm"
            onClick={onShowDetails}
          >
            <EyeIcon className="h-4 w-4" />
          </Button>

          {item.status === 'error' && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onRetry(item.id)}
              className="text-muted-foreground hover:text-foreground"
            >
              <ArrowPathIcon className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      {item.status !== 'completed' && item.status !== 'error' && (
        <div className="mt-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-muted-foreground">
              {item.progress}% complete
            </span>
          </div>
          <div className="w-full bg-secondary rounded-full h-1.5">
            <div
              className="bg-primary h-1.5 rounded-full transition-all duration-300"
              style={{ width: `${item.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Error Message */}
      {item.error && (
        <div className="mt-2 p-2 bg-destructive/10 border border-destructive/20 rounded text-xs text-destructive">
          {item.error}
        </div>
      )}
    </div>
  );
};

// Processing Chart Component
interface ProcessingChartProps {
  data: TimeSeriesData[];
}

const ProcessingChart: React.FC<ProcessingChartProps> = ({ data }) => {
  if (data.length === 0) {
    return (
      <div className="p-8 text-center text-muted-foreground">
        <ChartBarIcon className="h-12 w-12 mx-auto mb-4 opacity-50" />
        <p>No data available yet</p>
      </div>
    );
  }

  // Simple SVG chart implementation
  const maxCompleted = Math.max(...data.map(d => d.completed), 1);
  const maxFailed = Math.max(...data.map(d => d.failed), 1);
  const maxProcessing = Math.max(...data.map(d => d.processing), 1);
  const maxValue = Math.max(maxCompleted, maxFailed, maxProcessing);

  const width = 600;
  const height = 300;
  const padding = 40;

  return (
    <div className="space-y-4">
      <div className="flex items-center space-x-6 text-sm">
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 bg-green-500 rounded-full" />
          <span>Completed</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 bg-red-500 rounded-full" />
          <span>Failed</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 bg-blue-500 rounded-full" />
          <span>Processing</span>
        </div>
      </div>

      <svg width={width} height={height} className="w-full h-auto">
        {/* Grid lines */}
        {Array.from({ length: 5 }, (_, i) => {
          const y = padding + (height - 2 * padding) * (i / 4);
          return (
            <line
              key={i}
              x1={padding}
              y1={y}
              x2={width - padding}
              y2={y}
              stroke="#e5e7eb"
              strokeWidth="1"
            />
          );
        })}

        {/* Completed line */}
        <polyline
          fill="none"
          stroke="#10b981"
          strokeWidth="2"
          points={data.map((d, i) => {
            const x = padding + (width - 2 * padding) * (i / Math.max(data.length - 1, 1));
            const y = height - padding - ((height - 2 * padding) * (d.completed / maxValue));
            return `${x},${y}`;
          }).join(' ')}
        />

        {/* Failed line */}
        <polyline
          fill="none"
          stroke="#ef4444"
          strokeWidth="2"
          points={data.map((d, i) => {
            const x = padding + (width - 2 * padding) * (i / Math.max(data.length - 1, 1));
            const y = height - padding - ((height - 2 * padding) * (d.failed / maxValue));
            return `${x},${y}`;
          }).join(' ')}
        />

        {/* Processing line */}
        <polyline
          fill="none"
          stroke="#3b82f6"
          strokeWidth="2"
          points={data.map((d, i) => {
            const x = padding + (width - 2 * padding) * (i / Math.max(data.length - 1, 1));
            const y = height - padding - ((height - 2 * padding) * (d.processing / maxValue));
            return `${x},${y}`;
          }).join(' ')}
        />

        {/* Data points */}
        {data.map((d, i) => {
          const x = padding + (width - 2 * padding) * (i / Math.max(data.length - 1, 1));

          return (
            <g key={i}>
              {/* Completed point */}
              <circle
                cx={x}
                cy={height - padding - ((height - 2 * padding) * (d.completed / maxValue))}
                r="3"
                fill="#10b981"
              />
              {/* Failed point */}
              <circle
                cx={x}
                cy={height - padding - ((height - 2 * padding) * (d.failed / maxValue))}
                r="3"
                fill="#ef4444"
              />
              {/* Processing point */}
              <circle
                cx={x}
                cy={height - padding - ((height - 2 * padding) * (d.processing / maxValue))}
                r="3"
                fill="#3b82f6"
              />
            </g>
          );
        })}
      </svg>

      <div className="text-xs text-muted-foreground text-center">
        Last {data.length} updates
      </div>
    </div>
  );
};

// Processing Item Details Component
interface ProcessingItemDetailsProps {
  item: UploadQueueItem;
}

const ProcessingItemDetails: React.FC<ProcessingItemDetailsProps> = ({ item }) => {
  const getFileTypeCategory = (file: File): string => {
    if (file.type === 'application/pdf') return 'PDF Document';
    if (file.type === 'text/plain') return 'Text Document';
    if (file.type.startsWith('image/')) return 'Image';
    if (file.type.startsWith('audio/')) return 'Audio';
    if (file.type.startsWith('video/')) return 'Video';
    return 'Other';
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  };

  const formatTimestamp = (timestamp: number): string => {
    return new Date(timestamp).toLocaleString();
  };

  const getElapsedTime = (): string => {
    if (!item.uploadStartTime) return 'N/A';
    const startTime = item.uploadStartTime;
    const endTime = item.completedAt || Date.now();
    const elapsedSeconds = (endTime - startTime) / 1000;

    if (elapsedSeconds < 60) return `${Math.round(elapsedSeconds)}s`;
    if (elapsedSeconds < 3600) return `${Math.round(elapsedSeconds / 60)}m ${Math.round(elapsedSeconds % 60)}s`;
    return `${Math.floor(elapsedSeconds / 3600)}h ${Math.round((elapsedSeconds % 3600) / 60)}m`;
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-sm font-medium text-muted-foreground">File Name</label>
          <p className="text-sm text-foreground">{item.file.name}</p>
        </div>
        <div>
          <label className="text-sm font-medium text-muted-foreground">File Type</label>
          <p className="text-sm text-foreground">{getFileTypeCategory(item.file)}</p>
        </div>
        <div>
          <label className="text-sm font-medium text-muted-foreground">File Size</label>
          <p className="text-sm text-foreground">{formatFileSize(item.file.size)}</p>
        </div>
        <div>
          <label className="text-sm font-medium text-muted-foreground">Status</label>
          <Badge className="mt-1">{item.status}</Badge>
        </div>
        <div>
          <label className="text-sm font-medium text-muted-foreground">Progress</label>
          <p className="text-sm text-foreground">{item.progress}%</p>
        </div>
        <div>
          <label className="text-sm font-medium text-muted-foreground">Elapsed Time</label>
          <p className="text-sm text-foreground">{getElapsedTime()}</p>
        </div>
        {item.jobId && (
          <div>
            <label className="text-sm font-medium text-muted-foreground">Job ID</label>
            <p className="text-sm text-foreground font-mono">{item.jobId}</p>
          </div>
        )}
        {item.documentId && (
          <div>
            <label className="text-sm font-medium text-muted-foreground">Document ID</label>
            <p className="text-sm text-foreground font-mono">{item.documentId}</p>
          </div>
        )}
      </div>

      {item.uploadStartTime && (
        <div>
          <label className="text-sm font-medium text-muted-foreground">Upload Started</label>
          <p className="text-sm text-foreground">{formatTimestamp(item.uploadStartTime)}</p>
        </div>
      )}

      {item.processingStartTime && (
        <div>
          <label className="text-sm font-medium text-muted-foreground">Processing Started</label>
          <p className="text-sm text-foreground">{formatTimestamp(item.processingStartTime)}</p>
        </div>
      )}

      {item.completedAt && (
        <div>
          <label className="text-sm font-medium text-muted-foreground">Completed At</label>
          <p className="text-sm text-foreground">{formatTimestamp(item.completedAt)}</p>
        </div>
      )}

      {item.error && (
        <div>
          <label className="text-sm font-medium text-muted-foreground">Error Details</label>
          <div className="mt-1 p-3 bg-destructive/10 border border-destructive/20 rounded text-sm text-destructive">
            {item.error}
          </div>
        </div>
      )}

      {item.uploadResponse && (
        <div>
          <label className="text-sm font-medium text-muted-foreground">Upload Response</label>
          <div className="mt-1 p-3 bg-muted/50 rounded text-xs font-mono">
            <pre>{JSON.stringify(item.uploadResponse, null, 2)}</pre>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProcessingDashboard;