import React, { useState, useEffect, useMemo } from 'react';
import {
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  DocumentTextIcon,
  EyeIcon,
  PhotoIcon,
  MusicalNoteIcon,
  VideoCameraIcon,
  ArrowPathIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';
import { Document } from '@/types';
import { api } from '@/services/api-client';
import { Badge } from '@/components/ui/badge';
import { ErrorDisplay } from './ErrorDisplay';

// Mirrors ProcessingStatusResponse (GET /processing/documents/{id}/status),
// same contract uploadService.ts polls (#1489).
interface ProcessingStatusResponse {
  document_id: string;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed' | string;
  is_embedded: boolean;
  is_indexed: boolean;
  processing_error: string | null;
}

const POLL_INTERVAL_MS = 3000;

const toDocumentProcessingStatus = (
  status: ProcessingStatusResponse['processing_status']
): Document['processing_status'] => {
  if (status === 'pending') return 'queued';
  if (status === 'completed') return 'indexed';
  if (status === 'processing' || status === 'failed') return status;
  return 'queued';
};

interface PollState {
  status: Document['processing_status'] | null;
  error: string | null;
  lastUpdate: Date | null;
}

interface UseProcessingStatusPollingReturn extends PollState {
  isPolling: boolean;
}

const isTerminalStatus = (
  status: Document['processing_status'] | null
): boolean => status === 'indexed' || status === 'failed';

/**
 * Polls GET /processing/documents/{id}/status while `enabled` is true and
 * stops once the document reaches a terminal status (indexed/failed) or is
 * unmounted. Replaces the WebSocket subscription that never worked
 * (R4-H1/H2/H3: handshake/payload-shape mismatch, server emitted no events).
 */
function useProcessingStatusPolling(
  documentId: string,
  enabled: boolean
): UseProcessingStatusPollingReturn {
  const [state, setState] = useState<PollState>({
    status: null,
    error: null,
    lastUpdate: null,
  });

  useEffect(() => {
    if (!enabled) {
      return;
    }

    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;

    const poll = async (): Promise<void> => {
      try {
        const response = await api.get<ProcessingStatusResponse>(
          `/processing/documents/${documentId}/status`
        );
        if (cancelled) return;

        const status = toDocumentProcessingStatus(response.processing_status);
        setState({
          status,
          error: response.processing_error,
          lastUpdate: new Date(),
        });

        if (!isTerminalStatus(status)) {
          timeoutId = setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch {
        if (cancelled) return;
        setState((prev) => ({ ...prev, lastUpdate: new Date() }));
        timeoutId = setTimeout(poll, POLL_INTERVAL_MS);
      }
    };

    void poll();

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [documentId, enabled]);

  return { ...state, isPolling: enabled && !isTerminalStatus(state.status) };
}

export interface ProcessingStatusProps {
  document: Document;
  jobId?: string;

  // Legacy props for backward compatibility
  currentStep?: string;
  progress?: number;
  estimatedRemainingSeconds?: number;
  error?: string;

  // Poll GET /processing/documents/{id}/status while true
  enableRealtime?: boolean;

  // Callbacks
  onRetry?: () => void;
  onViewDetails?: () => void;
  onStatusChange?: (status: Document['processing_status']) => void;

  // Display options
  className?: string;
  compact?: boolean;
}

interface ProcessingStep {
  id: string;
  name: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'error' | 'skipped';
  duration?: number;
  error?: string;
  startTime?: string;
  endTime?: string;
  icon?: React.ComponentType<{ className?: string }>;
}

const getProcessingSteps = (document: Document): ProcessingStep[] => {
  const steps: ProcessingStep[] = [
    {
      id: 'validation',
      name: 'File Validation',
      description: 'Validating file format and integrity',
      status: 'pending',
      icon: ClockIcon,
    },
  ];

  // Add OCR step for PDF and images
  if (
    document.file_type === 'pdf' ||
    document.file_type === 'jpg' ||
    document.file_type === 'png'
  ) {
    steps.push({
      id: 'ocr',
      name: 'Text Extraction',
      description: 'Extracting text using OCR technology',
      status: 'pending',
      icon: DocumentTextIcon,
    });
  }

  // Add transcription step for audio/video
  if (document.file_type === 'mp3' || document.file_type === 'mp4') {
    steps.push({
      id: 'transcription',
      name: 'Audio/Video Transcription',
      description: 'Converting audio/video to text using speech recognition',
      status: 'pending',
      icon: MusicalNoteIcon,
    });

    // Add frame extraction for video
    if (document.file_type === 'mp4') {
      steps.push({
        id: 'frame_extraction',
        name: 'Frame Extraction',
        description: 'Extracting key frames from video',
        status: 'pending',
        icon: PhotoIcon,
      });
    }
  }

  // Common processing steps
  steps.push(
    {
      id: 'entity_extraction',
      name: 'Entity Extraction',
      description: 'Identifying people, organizations, and key entities',
      status: 'pending',
      icon: InformationCircleIcon,
    },
    {
      id: 'embedding',
      name: 'Vector Embedding',
      description: 'Creating semantic embeddings for search',
      status: 'pending',
      icon: EyeIcon,
    },
    {
      id: 'indexing',
      name: 'Search Indexing',
      description: 'Adding document to search index',
      status: 'pending',
      icon: CheckCircleIcon,
    }
  );

  return steps;
};

// Pure derivation of step state from the current props — replaces the old
// effect-driven `setSteps` chain (rendered progress is a function of props,
// not independent state that needs synchronizing).
const applyStepProgress = (
  baseSteps: ProcessingStep[],
  currentStep: string | undefined,
  progress: number,
  error: string | null | undefined,
  isIndexed: boolean
): ProcessingStep[] => {
  let steps = baseSteps;

  if (currentStep && progress > 0) {
    const currentStepIndex = steps.findIndex(
      (step) => step.id === currentStep
    );

    if (currentStepIndex !== -1) {
      steps = steps.map((step, i) => {
        if (i < currentStepIndex && step.status === 'pending') {
          return { ...step, status: 'completed', endTime: new Date().toISOString() };
        }
        if (i === currentStepIndex && step.status === 'pending') {
          return { ...step, status: 'in_progress', startTime: new Date().toISOString() };
        }
        return step;
      });
    }
  }

  if (error && error.length > 0) {
    const lastInProgressIndex = steps.findIndex(
      (step) => step.status === 'in_progress'
    );
    if (lastInProgressIndex !== -1) {
      steps = steps.map((step, i) =>
        i === lastInProgressIndex
          ? { ...step, status: 'error', error, endTime: new Date().toISOString() }
          : step
      );
    }
  }

  if (isIndexed) {
    steps = steps.map((step) => ({
      ...step,
      status: 'completed' as const,
      endTime: new Date().toISOString(),
    }));
  }

  return steps;
};

const getStepIcon = (step: ProcessingStep): React.ReactElement => {
  const iconClass = 'h-5 w-5';
  switch (step.status) {
    case 'in_progress':
      return (
        <div
          className={cn(
            iconClass,
            'animate-spin rounded-full border-2 border-primary border-t-transparent'
          )}
        />
      );
    case 'completed':
      return <CheckCircleIcon className={cn(iconClass, 'text-green-600')} />;
    case 'error':
      return <XCircleIcon className={cn(iconClass, 'text-destructive')} />;
    case 'skipped':
      return <div className={cn(iconClass, 'text-muted-foreground')} />;
    default:
      return step.icon ? (
        <step.icon className={cn(iconClass, 'text-muted-foreground')} />
      ) : (
        <ClockIcon className={cn(iconClass, 'text-muted-foreground')} />
      );
  }
};

const formatDuration = (startTime: string, endTime?: string): string => {
  const start = new Date(startTime);
  const end = endTime ? new Date(endTime) : new Date();
  const duration = end.getTime() - start.getTime();

  if (duration < 1000) return '< 1s';
  if (duration < 60000) return `${Math.round(duration / 1000)}s`;
  if (duration < 3600000) return `${Math.round(duration / 60000)}m`;
  return `${Math.round(duration / 3600000)}h`;
};

const getStepProgress = (steps: ProcessingStep[]): number => {
  const completedSteps = steps.filter(
    (step) => step.status === 'completed'
  ).length;
  return Math.round((completedSteps / steps.length) * 100);
};

const formatLastUpdate = (lastUpdate: Date): string => {
  const now = new Date();
  const diffMs = now.getTime() - lastUpdate.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 5) return 'just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
};

export const ProcessingStatus: React.FC<ProcessingStatusProps> = ({
  document,
  jobId,
  currentStep: propCurrentStep,
  progress: propProgress = 0,
  estimatedRemainingSeconds: propEstimatedTime,
  error: propError,
  enableRealtime = false,
  onRetry,
  onViewDetails,
  onStatusChange,
  className,
  compact = false,
}) => {
  const baseSteps = useMemo(() => getProcessingSteps(document), [document]);
  const [expanded, setExpanded] = useState(false);

  // Poll processing status when enableRealtime is true
  const realtime = useProcessingStatusPolling(
    document.id,
    enableRealtime &&
      (document.processing_status === 'processing' ||
        document.processing_status === 'queued')
  );

  // The status-poll endpoint only reports terminal state + error, not
  // step/progress detail, so those still come from props/caller-driven state.
  const useRealtimeData = enableRealtime && realtime.status !== null;
  const currentStep = propCurrentStep;
  const progress = propProgress;
  const estimatedRemainingSeconds = propEstimatedTime;
  const error = useRealtimeData ? realtime.error : propError;

  // Notify parent when status changes (from polling)
  useEffect(() => {
    if (
      useRealtimeData &&
      onStatusChange &&
      realtime.status &&
      realtime.status !== document.processing_status
    ) {
      onStatusChange(realtime.status);
    }
  }, [
    useRealtimeData,
    realtime.status,
    document.processing_status,
    onStatusChange,
  ]);

  // Derived, not effect-driven: rendered step state is a pure function of
  // the current props/poll result, so it doesn't need its own copy in state.
  const steps = useMemo(
    () =>
      applyStepProgress(
        baseSteps,
        currentStep,
        progress,
        error,
        document.processing_status === 'indexed'
      ),
    [baseSteps, currentStep, progress, error, document.processing_status]
  );

  const status = document.processing_status;
  const isCompleted = status === 'indexed';
  const hasError = status === 'failed' || error;
  // If completed, always show 100%; otherwise use progress or step-based calculation
  const overallProgress = error
    ? 0
    : isCompleted
      ? 100
      : progress || getStepProgress(steps);

  const formatTimeRemaining = (seconds?: number): string => {
    if (!seconds) return 'Calculating...';
    if (seconds < 60) return `~ ${Math.ceil(seconds)}s`;
    const minutes = Math.ceil(seconds / 60);
    return `~ ${minutes}m`;
  };

  const getStatusIcon = (): React.ReactElement => {
    if (isCompleted)
      return <CheckCircleIcon className="h-6 w-6 text-green-600" />;
    if (hasError) return <XCircleIcon className="h-6 w-6 text-destructive" />;
    return (
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
    );
  };

  const getStatusText = (): string => {
    if (isCompleted) return 'Processing completed';
    if (hasError) return 'Processing failed';
    if (status === 'queued') return 'Queued for processing';
    if (status === 'processing') return currentStep || 'Processing...';
    return 'Preparing to process';
  };

  const getFileIcon = (): React.ReactElement => {
    switch (document.file_type) {
      case 'pdf':
        return <DocumentTextIcon className="h-8 w-8 text-red-600" />;
      case 'txt':
        return <DocumentTextIcon className="h-8 w-8 text-blue-600" />;
      case 'jpg':
      case 'png':
        return <PhotoIcon className="h-8 w-8 text-green-600" />;
      case 'mp3':
        return <MusicalNoteIcon className="h-8 w-8 text-purple-600" />;
      case 'mp4':
        return <VideoCameraIcon className="h-8 w-8 text-orange-600" />;
      default:
        return <DocumentTextIcon className="h-8 w-8 text-foreground" />;
    }
  };

  if (compact) {
    return (
      <div className={cn('flex items-center space-x-2 text-sm', className)}>
        <div className="flex items-center space-x-2 flex-1 min-w-0">
          {getStatusIcon()}
          <span className="text-muted-foreground truncate">
            {getStatusText()}
          </span>
          {enableRealtime && realtime.isPolling && (
            <Badge variant="default" className="text-xs px-1.5 py-0">
              <span className="inline-block w-1.5 h-1.5 bg-green-500 rounded-full mr-1 animate-pulse" />
              Live
            </Badge>
          )}
          {document.processing_error && (
            <span className="text-destructive truncate">
              • {document.processing_error}
            </span>
          )}
        </div>
        <div className="flex items-center space-x-2 shrink-0">
          <div className="relative w-16 h-2 bg-muted rounded-full overflow-hidden">
            <div
              className={cn(
                'h-full transition-all duration-500 ease-out rounded-full',
                isCompleted && 'bg-green-600',
                hasError && 'bg-destructive',
                !isCompleted && !hasError && 'bg-primary'
              )}
              style={{ width: `${overallProgress}%` }}
            />
          </div>
          <span className="text-xs text-muted-foreground w-8 text-right">
            {overallProgress}%
          </span>
          {hasError && onRetry && (
            <button
              onClick={onRetry}
              className="p-1 text-muted-foreground hover:text-foreground hover:bg-accent rounded transition-colors"
              aria-label="Retry processing"
            >
              <ArrowPathIcon className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={cn('bg-card border rounded-lg p-6 space-y-4', className)}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-4">
          {getFileIcon()}
          <div className="flex-1">
            <h3 className="text-lg font-medium text-foreground flex items-center space-x-2">
              <span>{document.title}</span>
              {getStatusIcon()}
              {enableRealtime && (
                <Badge
                  variant={realtime.isPolling ? 'default' : 'secondary'}
                  className="text-xs"
                >
                  {realtime.isPolling ? (
                    <>
                      <span className="inline-block w-2 h-2 bg-green-500 rounded-full mr-1 animate-pulse" />
                      Live
                    </>
                  ) : (
                    <>
                      <span className="inline-block w-2 h-2 bg-muted-foreground rounded-full mr-1" />
                      Offline
                    </>
                  )}
                </Badge>
              )}
            </h3>
            <p className="text-sm text-muted-foreground">{getStatusText()}</p>
            {jobId && (
              <p className="text-xs text-muted-foreground">Job ID: {jobId}</p>
            )}
            {enableRealtime && realtime.lastUpdate && (
              <p className="text-xs text-muted-foreground">
                Last updated: {formatLastUpdate(realtime.lastUpdate)}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <div className="text-right">
            <div className="text-lg font-medium text-foreground">
              {overallProgress}%
            </div>
            <div className="text-sm text-muted-foreground">
              {status === 'processing' && estimatedRemainingSeconds && (
                <span>{formatTimeRemaining(estimatedRemainingSeconds)}</span>
              )}
            </div>
          </div>

          <button
            onClick={() => setExpanded(!expanded)}
            className="p-2 text-muted-foreground hover:text-foreground hover:bg-accent rounded transition-colors"
            aria-label={expanded ? 'Collapse details' : 'Expand details'}
          >
            <InformationCircleIcon className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="relative w-full h-3 bg-muted rounded-full overflow-hidden">
          <div
            className={cn(
              'h-full transition-all duration-500 ease-out rounded-full',
              isCompleted && 'bg-green-600',
              hasError && 'bg-destructive',
              !isCompleted && !hasError && 'bg-primary'
            )}
            style={{ width: `${overallProgress}%` }}
          />
        </div>

        <div className="flex justify-between text-xs text-muted-foreground">
          <span>{currentStep || 'Processing...'}</span>
          <span>{overallProgress}% complete</span>
        </div>
      </div>

      {/* Processing Steps */}
      {expanded && (
        <div className="space-y-3 pt-4 border-t">
          <h4 className="text-sm font-medium text-foreground">
            Processing Steps
          </h4>
          <div className="space-y-2">
            {steps.map((step) => (
              <div
                key={step.id}
                className={cn(
                  'flex items-center justify-between p-3 rounded-md transition-colors',
                  step.status === 'in_progress' && 'bg-primary/5',
                  step.status === 'error' && 'bg-destructive/5'
                )}
              >
                <div className="flex items-center space-x-3">
                  <div className="flex items-center justify-center">
                    {getStepIcon(step)}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center space-x-2">
                      <p
                        className={cn(
                          'text-sm font-medium',
                          step.status === 'in_progress'
                            ? 'text-foreground'
                            : 'text-muted-foreground'
                        )}
                      >
                        {step.name}
                      </p>
                      {step.duration && step.startTime && (
                        <span className="text-xs text-muted-foreground">
                          ({formatDuration(step.startTime, step.endTime)})
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {step.description}
                    </p>
                    {step.error && (
                      <p className="text-xs text-destructive mt-1">
                        {step.error}
                      </p>
                    )}
                  </div>
                </div>

                <div className="text-xs text-muted-foreground">
                  {step.status === 'completed' && '✓ Done'}
                  {step.status === 'in_progress' && 'Processing...'}
                  {step.status === 'error' && 'Failed'}
                  {step.status === 'skipped' && 'Skipped'}
                  {step.status === 'pending' && 'Pending'}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <ErrorDisplay
          error={error}
          severity="error"
          errorType="processing"
          onRetry={onRetry}
        />
      )}

      {/* Actions */}
      <div className="flex justify-between items-center pt-4 border-t">
        <div className="text-xs text-muted-foreground">
          {status === 'processing' &&
            'Processing may take several minutes for large files'}
          {isCompleted && 'Document is ready for search and retrieval'}
          {hasError && 'Please try processing the file again'}
          {status === 'queued' &&
            'Your file is in the queue and will be processed shortly'}
        </div>

        <div className="flex items-center space-x-2">
          {onViewDetails && (
            <button
              onClick={onViewDetails}
              className="text-sm text-primary hover:text-primary/80 transition-colors"
            >
              View Details
            </button>
          )}

          {hasError && onRetry && (
            <button
              onClick={onRetry}
              className="inline-flex items-center px-3 py-1 text-sm font-medium text-primary hover:text-primary/80 transition-colors"
            >
              <ArrowPathIcon className="h-3 w-3 mr-1" />
              Retry
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProcessingStatus;
