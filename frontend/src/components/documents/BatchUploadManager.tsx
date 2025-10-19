import React, { useState, useCallback, useRef, useEffect } from 'react';
import { CloudArrowUpIcon, PauseIcon, PlayIcon, XMarkIcon, CheckCircleIcon } from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';
import { DocumentUploader } from './DocumentUploader';
import { CompactUploadProgress } from './UploadProgress';
import { FileValidationError } from '@/utils/fileValidation';
import { Document, DocumentUpload } from '@/types';
import { useAuth } from '@/hooks/useAuth';

export interface BatchUploadManagerProps {
  onUploadComplete?: (documents: Document[]) => void;
  onUploadError?: (error: string) => void;
  maxConcurrentUploads?: number;
  className?: string;
}

interface UploadJob extends DocumentUpload {
  file: File;
  retryCount: number;
  maxRetries: number;
}

interface BatchUploadState {
  jobs: UploadJob[];
  isUploading: boolean;
  isPaused: boolean;
  completedCount: number;
  failedCount: number;
  totalProgress: number;
}

const MAX_CONCURRENT_UPLOADS = 3;
const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 2000;

export const BatchUploadManager: React.FC<BatchUploadManagerProps> = ({
  onUploadComplete,
  onUploadError,
  maxConcurrentUploads = MAX_CONCURRENT_UPLOADS,
  className,
}) => {
  const { user } = useAuth();
  const [uploadState, setUploadState] = useState<BatchUploadState>({
    jobs: [],
    isUploading: false,
    isPaused: false,
    completedCount: 0,
    failedCount: 0,
    totalProgress: 0,
  });

  // Store validation errors for display (currently unused but kept for future enhancement)
  const [, setValidationErrors] = useState<FileValidationError[]>([]);
  const activeUploads = useRef<Map<string, AbortController>>(new Map());
  const uploadQueue = useRef<string[]>([]);
  const isPausedRef = useRef<boolean>(false);

  // Sync isPausedRef with uploadState.isPaused
  useEffect(() => {
    isPausedRef.current = uploadState.isPaused;
  }, [uploadState.isPaused]);

  const calculateTotalProgress = useCallback((jobs: UploadJob[]): number => {
    if (jobs.length === 0) return 0;
    const totalProgress = jobs.reduce((sum, job) => sum + job.progress, 0);
    return Math.round(totalProgress / jobs.length);
  }, []);

  const updateJobStatus = useCallback((jobId: string, updates: Partial<UploadJob>) => {
    setUploadState(prev => {
      const updatedJobs = prev.jobs.map(job =>
        job.id === jobId ? { ...job, ...updates } : job
      );

      const completedCount = updatedJobs.filter(job => job.status === 'completed').length;
      const failedCount = updatedJobs.filter(job => job.status === 'error').length;
      const totalProgress = calculateTotalProgress(updatedJobs);

      return {
        ...prev,
        jobs: updatedJobs,
        completedCount,
        failedCount,
        totalProgress,
      };
    });
  }, [calculateTotalProgress]);

  const simulateUploadProgress = useCallback(async (jobId: string, _file: File) => {
    const duration = 2000 + Math.random() * 3000; // 2-5 seconds
    const steps = 20;
    const stepDuration = duration / steps;

    for (let i = 0; i <= steps; i++) {
      await new Promise(resolve => setTimeout(resolve, stepDuration));

      setUploadState(prev => {
        if (prev.isPaused) return prev;

        const updatedJobs = prev.jobs.map(job => {
          if (job.id === jobId && job.status === 'uploading') {
            const progress = Math.round((i / steps) * 100);
            return { ...job, progress };
          }
          return job;
        });

        return {
          ...prev,
          jobs: updatedJobs,
          totalProgress: calculateTotalProgress(updatedJobs),
        };
      });
    }
  }, [calculateTotalProgress]);

  const simulateProcessing = useCallback(async (_jobId: string) => {
    // Simulate processing stages
    const stages = [
      { name: 'Validating file format', duration: 500 },
      { name: 'Extracting text (OCR)', duration: 1500 },
      { name: 'Creating embeddings', duration: 1000 },
      { name: 'Indexing in search', duration: 800 },
    ];

    for (const stage of stages) {
      await new Promise(resolve => setTimeout(resolve, stage.duration));

      if (isPausedRef.current) {
        await new Promise(resolve => {
          const checkInterval = setInterval(() => {
            if (!isPausedRef.current) {
              clearInterval(checkInterval);
              resolve(undefined);
            }
          }, 100);
        });
      }
    }
  }, []); // Removed uploadState.isPaused from dependencies

  const processUpload = useCallback(async (job: UploadJob): Promise<void> => {
    const controller = new AbortController();
    activeUploads.current.set(job.id, controller);

    try {
      // Simulate upload progress
      updateJobStatus(job.id, { status: 'uploading', progress: 0 });
      await simulateUploadProgress(job.id, job.file);

      // Simulate processing
      const generatedJobId = `job-${job.id}`;
      updateJobStatus(job.id, {
        status: 'processing',
        progress: 100,
        jobId: generatedJobId,
        documentId: `doc-${job.id}`
      });
      await simulateProcessing(job.id);

      // Mark as completed
      updateJobStatus(job.id, { status: 'completed', progress: 100 });

    } catch (error) {
      console.error(`Upload failed for ${job.file.name}:`, error);

      // Retry logic
      if (job.retryCount < job.maxRetries) {
        updateJobStatus(job.id, {
          status: 'pending',
          retryCount: job.retryCount + 1,
          error: `Retrying... (${job.retryCount + 1}/${job.maxRetries})`
        });

        setTimeout(() => {
          processUpload(job);
        }, RETRY_DELAY_MS * (job.retryCount + 1));
      } else {
        updateJobStatus(job.id, {
          status: 'error',
          error: 'Upload failed after maximum retries'
        });
        onUploadError?.(`Failed to upload ${job.file.name} after ${job.maxRetries} attempts`);
      }
    } finally {
      activeUploads.current.delete(job.id);
    }
  }, [updateJobStatus, simulateUploadProgress, simulateProcessing, onUploadError]);

  const startUploadQueue = useCallback(() => {
    const pendingJobs = uploadState.jobs.filter(job => job.status === 'pending');
    uploadQueue.current = pendingJobs.map(job => job.id);

    const processNext = () => {
      while (activeUploads.current.size < maxConcurrentUploads && uploadQueue.current.length > 0) {
        const jobId = uploadQueue.current.shift()!;
        const job = uploadState.jobs.find(j => j.id === jobId);
        if (job && !uploadState.isPaused) {
          processUpload(job);
        }
      }
    };

    processNext();

    // Monitor for completed jobs to start next ones
    const interval = setInterval(() => {
      if (uploadQueue.current.length === 0 && activeUploads.current.size === 0) {
        clearInterval(interval);

        // Check if all jobs are completed
        const allJobs = uploadState.jobs;
        const completedJobs = allJobs.filter(job => job.status === 'completed');
        const failedJobs = allJobs.filter(job => job.status === 'error');

        if (completedJobs.length + failedJobs.length === allJobs.length) {
          setUploadState(prev => ({ ...prev, isUploading: false }));

          if (completedJobs.length > 0) {
            // Validate auth info before creating documents
            if (!user || !user.id || !user.organization_id) {
              onUploadError?.('Unable to complete upload: User authentication information is missing');
              return;
            }

            const documents: Document[] = completedJobs.map(job => ({
              id: job.documentId || `doc-${job.id}`,
              user_id: user.id,
              organization_id: user.organization_id,
              title: job.file.name,
              filename: job.file.name,
              file_type: job.file.name.split('.').pop()?.toLowerCase() as Document['file_type'],
              file_size: job.file.size,
              processing_status: 'indexed' as const,
              upload_timestamp: new Date().toISOString(),
              processing_completed_at: new Date().toISOString(),
              metadata: {},
            }));

            onUploadComplete?.(documents);
          }
        }
      } else {
        processNext();
      }
    }, 100);
  }, [uploadState.jobs, uploadState.isPaused, maxConcurrentUploads, processUpload, onUploadComplete, onUploadError, user]);

  const handleFilesSelected = useCallback((files: File[]) => {
    const newJobs: UploadJob[] = files.map(file => ({
      file,
      id: Math.random().toString(36).substr(2, 9),
      progress: 0,
      status: 'pending',
      retryCount: 0,
      maxRetries: MAX_RETRIES,
    }));

    setUploadState(prev => ({
      ...prev,
      jobs: [...prev.jobs, ...newJobs],
    }));

    setValidationErrors([]);
  }, []);

  const handleFilesRemoved = useCallback((fileIds: string[]) => {
    // Cancel active uploads
    fileIds.forEach(id => {
      const controller = activeUploads.current.get(id);
      if (controller) {
        controller.abort();
        activeUploads.current.delete(id);
      }

      // Remove from queue
      const queueIndex = uploadQueue.current.indexOf(id);
      if (queueIndex > -1) {
        uploadQueue.current.splice(queueIndex, 1);
      }
    });

    setUploadState(prev => {
      const updatedJobs = prev.jobs.filter(job => !fileIds.includes(job.id));
      const completedCount = updatedJobs.filter(job => job.status === 'completed').length;
      const failedCount = updatedJobs.filter(job => job.status === 'error').length;
      const totalProgress = calculateTotalProgress(updatedJobs);

      return {
        ...prev,
        jobs: updatedJobs,
        completedCount,
        failedCount,
        totalProgress,
      };
    });
  }, [calculateTotalProgress]);

  const handleValidationErrors = useCallback((errors: FileValidationError[]) => {
    setValidationErrors(errors);
  }, []);

  const startUpload = useCallback(() => {
    setUploadState(prev => ({ ...prev, isUploading: true, isPaused: false }));
    setTimeout(startUploadQueue, 100);
  }, [startUploadQueue]);

  const pauseUpload = useCallback(() => {
    setUploadState(prev => ({ ...prev, isPaused: true }));
  }, []);

  const resumeUpload = useCallback(() => {
    setUploadState(prev => ({ ...prev, isPaused: false }));
  }, []);

  const cancelUpload = useCallback(() => {
    // Cancel all active uploads
    activeUploads.current.forEach(controller => controller.abort());
    activeUploads.current.clear();
    uploadQueue.current = [];

    setUploadState(prev => ({
      ...prev,
      isUploading: false,
      isPaused: false,
    }));
  }, []);

  const clearCompleted = useCallback(() => {
    setUploadState(prev => ({
      ...prev,
      jobs: prev.jobs.filter(job => job.status !== 'completed' && job.status !== 'error'),
      completedCount: 0,
      failedCount: 0,
      totalProgress: calculateTotalProgress(
        prev.jobs.filter(job => job.status !== 'completed' && job.status !== 'error')
      ),
    }));
  }, [calculateTotalProgress]);

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const totalSize = uploadState.jobs.reduce((sum, job) => sum + job.file.size, 0);

  return (
    <div className={cn("space-y-6", className)}>
      {/* Upload Area */}
      <DocumentUploader
        onFilesSelected={handleFilesSelected}
        onFilesRemoved={handleFilesRemoved}
        onValidationErrors={handleValidationErrors}
        currentQuotaUsed={0} // Would come from user context
        maxQuota={5 * 1024 * 1024 * 1024} // 5GB
      />

      {/* Batch Upload Controls */}
      {uploadState.jobs.length > 0 && (
        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-medium text-foreground">
                Batch Upload ({uploadState.jobs.length} files)
              </h3>
              <p className="text-sm text-muted-foreground">
                {formatFileSize(totalSize)} total • {uploadState.completedCount} completed • {uploadState.failedCount} failed
              </p>
            </div>

            <div className="flex items-center space-x-2">
              {!uploadState.isUploading ? (
                <button
                  onClick={startUpload}
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-primary-foreground bg-primary hover:bg-primary/90 transition-colors"
                >
                  <CloudArrowUpIcon className="h-4 w-4 mr-2" />
                  Start Upload
                </button>
              ) : (
                <>
                  {uploadState.isPaused ? (
                    <button
                      onClick={resumeUpload}
                      className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-primary-foreground bg-primary hover:bg-primary/90 transition-colors"
                    >
                      <PlayIcon className="h-4 w-4 mr-2" />
                      Resume
                    </button>
                  ) : (
                    <button
                      onClick={pauseUpload}
                      className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-foreground bg-card hover:bg-accent transition-colors"
                    >
                      <PauseIcon className="h-4 w-4 mr-2" />
                      Pause
                    </button>
                  )}

                  <button
                    onClick={cancelUpload}
                    className="inline-flex items-center px-4 py-2 border border-destructive text-sm font-medium rounded-md text-destructive hover:bg-destructive/10 transition-colors"
                  >
                    <XMarkIcon className="h-4 w-4 mr-2" />
                    Cancel
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Overall Progress */}
          {uploadState.isUploading && (
            <div className="mb-4">
              <div className="flex justify-between text-sm mb-2">
                <span>Overall Progress</span>
                <span>{uploadState.totalProgress}%</span>
              </div>
              <div className="w-full bg-muted rounded-full h-2">
                <div
                  className="bg-primary h-2 rounded-full transition-all duration-300"
                  style={{ width: `${uploadState.totalProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* File List */}
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {uploadState.jobs.map((job) => (
              <CompactUploadProgress
                key={job.id}
                progress={job.progress}
                status={job.status as any}
                fileName={job.file.name}
              />
            ))}
          </div>

          {/* Clear Completed */}
          {(uploadState.completedCount > 0 || uploadState.failedCount > 0) && !uploadState.isUploading && (
            <div className="pt-4 border-t">
              <button
                onClick={clearCompleted}
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Clear completed ({uploadState.completedCount + uploadState.failedCount})
              </button>
            </div>
          )}
        </div>
      )}

      {/* Summary */}
      {uploadState.completedCount > 0 && !uploadState.isUploading && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-center space-x-2">
            <CheckCircleIcon className="h-5 w-5 text-green-600" />
            <span className="text-sm font-medium text-green-900">
              Upload completed successfully!
            </span>
          </div>
          <p className="text-sm text-green-700 mt-1">
            {uploadState.completedCount} files have been uploaded and processed.
          </p>
        </div>
      )}
    </div>
  );
};

export default BatchUploadManager;