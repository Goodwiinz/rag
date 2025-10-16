import React from 'react';
import { CheckCircleIcon, ClockIcon, ExclamationTriangleIcon, XCircleIcon } from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';

export interface UploadStep {
  id: string;
  name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'error';
  duration?: number; // in milliseconds
  error?: string;
}

export interface UploadProgressProps {
  jobId: string;
  progress: number; // 0-100
  currentStep: string;
  estimatedRemainingSeconds?: number;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  steps?: UploadStep[];
  error?: string;
  className?: string;
}

const DEFAULT_UPLOAD_STEPS: UploadStep[] = [
  { id: 'upload', name: 'Uploading file', status: 'pending' },
  { id: 'validation', name: 'Validating file format', status: 'pending' },
  { id: 'ocr', name: 'Extracting text (OCR)', status: 'pending' },
  { id: 'transcription', name: 'Transcribing audio', status: 'pending' },
  { id: 'embedding', name: 'Creating embeddings', status: 'pending' },
  { id: 'indexing', name: 'Indexing in search', status: 'pending' },
];

const STEP_ICONS = {
  pending: ClockIcon,
  in_progress: 'spinner',
  completed: CheckCircleIcon,
  error: ExclamationTriangleIcon,
};

const STEP_COLORS = {
  pending: 'text-muted-foreground',
  in_progress: 'text-primary',
  completed: 'text-green-600',
  error: 'text-destructive',
};

export const UploadProgress: React.FC<UploadProgressProps> = ({
  jobId,
  progress,
  currentStep,
  estimatedRemainingSeconds,
  status,
  steps = DEFAULT_UPLOAD_STEPS,
  error,
  className,
}) => {
  const formatDuration = (milliseconds: number): string => {
    if (milliseconds < 1000) return '< 1s';
    const seconds = Math.floor(milliseconds / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  const formatEstimatedTime = (seconds?: number): string => {
    if (!seconds) return 'Calculating...';
    if (seconds < 60) return `~ ${Math.ceil(seconds)}s`;
    const minutes = Math.ceil(seconds / 60);
    return `~ ${minutes}m`;
  };

  const getProgressColor = (status: string): string => {
    switch (status) {
      case 'completed': return 'bg-green-600';
      case 'processing': return 'bg-primary';
      case 'failed': return 'bg-destructive';
      case 'queued': return 'bg-muted-foreground';
      default: return 'bg-muted';
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="h-5 w-5 text-green-600" />;
      case 'failed':
        return <XCircleIcon className="h-5 w-5 text-destructive" />;
      case 'processing':
        return (
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        );
      case 'queued':
        return <ClockIcon className="h-5 w-5 text-muted-foreground" />;
      default:
        return null;
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'completed': return 'Processing completed';
      case 'failed': return 'Processing failed';
      case 'processing': return 'Processing in progress';
      case 'queued': return 'Queued for processing';
      default: return 'Preparing to process';
    }
  };

  return (
    <div className={cn("bg-card border rounded-lg p-6 space-y-4", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          {getStatusIcon()}
          <div>
            <h3 className="font-medium text-foreground">{getStatusText()}</h3>
            <p className="text-sm text-muted-foreground">Job ID: {jobId}</p>
          </div>
        </div>

        <div className="text-right">
          <div className="text-lg font-medium text-foreground">{progress}%</div>
          <div className="text-sm text-muted-foreground">
            {status === 'processing' && estimatedRemainingSeconds && (
              <span>{formatEstimatedTime(estimatedRemainingSeconds)} remaining</span>
            )}
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="relative w-full h-2 bg-muted rounded-full overflow-hidden">
          <div
            className={cn(
              "h-full transition-all duration-300 ease-out rounded-full",
              getProgressColor(status)
            )}
            style={{ width: `${progress}%` }}
          />
        </div>

        <div className="flex justify-between text-xs text-muted-foreground">
          <span>{currentStep}</span>
          <span>{progress}% complete</span>
        </div>
      </div>

      {/* Processing Steps */}
      <div className="space-y-3">
        <h4 className="text-sm font-medium text-foreground">Processing Steps</h4>
        <div className="space-y-2">
          {steps.map((step, index) => {
            const Icon = STEP_ICONS[step.status];
            const colorClass = STEP_COLORS[step.status];

            return (
              <div
                key={step.id}
                className={cn(
                  "flex items-center justify-between p-2 rounded-md transition-colors",
                  step.status === 'in_progress' && "bg-primary/5",
                  step.status === 'error' && "bg-destructive/5"
                )}
              >
                <div className="flex items-center space-x-3">
                  <div className={cn("flex items-center justify-center w-5 h-5", colorClass)}>
                    {step.status === 'in_progress' ? (
                      <div className="h-4 w-4 animate-spin rounded-full border border-current border-t-transparent" />
                    ) : (
                      <Icon className="h-4 w-4" />
                    )}
                  </div>
                  <span className={cn(
                    "text-sm",
                    step.status === 'in_progress' ? "font-medium text-foreground" : "text-muted-foreground"
                  )}>
                    {step.name}
                  </span>
                </div>

                <div className="flex items-center space-x-2 text-xs text-muted-foreground">
                  {step.duration && (
                    <span>{formatDuration(step.duration)}</span>
                  )}
                  {step.error && (
                    <span className="text-destructive">{step.error}</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
          <div className="flex items-start space-x-2">
            <ExclamationTriangleIcon className="h-4 w-4 text-destructive flex-shrink-0 mt-0.5" />
            <div className="text-sm text-destructive">
              <p className="font-medium">Processing Error</p>
              <p className="mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Footer Actions */}
      <div className="flex justify-between items-center pt-2 border-t">
        <div className="text-xs text-muted-foreground">
          {status === 'processing' && "This may take a few minutes for large files"}
          {status === 'completed' && "File is ready for search"}
          {status === 'failed' && "Please try uploading the file again"}
          {status === 'queued' && "Your file is in the queue and will be processed shortly"}
        </div>

        {status === 'failed' && (
          <button className="text-sm text-primary hover:text-primary/80 transition-colors">
            Retry Upload
          </button>
        )}
      </div>
    </div>
  );
};

// Compact version for inline display
export interface CompactUploadProgressProps {
  progress: number;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  fileName: string;
  className?: string;
}

export const CompactUploadProgress: React.FC<CompactUploadProgressProps> = ({
  progress,
  status,
  fileName,
  className,
}) => {
  const getStatusIcon = () => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="h-4 w-4 text-green-600" />;
      case 'failed':
        return <XCircleIcon className="h-4 w-4 text-destructive" />;
      case 'processing':
        return (
          <div className="h-4 w-4 animate-spin rounded-full border border-primary border-t-transparent" />
        );
      case 'queued':
        return <ClockIcon className="h-4 w-4 text-muted-foreground" />;
      default:
        return null;
    }
  };

  const getProgressColor = (status: string): string => {
    switch (status) {
      case 'completed': return 'bg-green-600';
      case 'processing': return 'bg-primary';
      case 'failed': return 'bg-destructive';
      case 'queued': return 'bg-muted-foreground';
      default: return 'bg-muted';
    }
  };

  return (
    <div className={cn("flex items-center space-x-3 p-2 bg-card border rounded-md", className)}>
      {getStatusIcon()}

      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm font-medium text-foreground truncate">{fileName}</span>
          <span className="text-xs text-muted-foreground ml-2">{progress}%</span>
        </div>
        <div className="relative w-full h-1 bg-muted rounded-full overflow-hidden">
          <div
            className={cn("h-full transition-all duration-300 ease-out rounded-full", getProgressColor(status))}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    </div>
  );
};

export default UploadProgress;