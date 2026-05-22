import { useState, useEffect, useCallback, useRef } from 'react';
import {
  uploadService,
  UploadQueueItem,
  UploadStats,
} from '@/services/uploadService';
import { FileValidationError, validateFileBatch } from '@/utils/fileValidation';
import { UPLOAD_LIMITS } from '@/types';
import { useDocumentProcessingUpdates } from '@/hooks/useWebSocket';

export interface UseDocumentUploadOptions {
  maxConcurrentUploads?: number;
  maxFileSize?: number;
  maxFiles?: number;
  allowedTypes?: string[];
  currentQuotaUsed?: number;
  maxQuota?: number;
  autoCleanup?: boolean;
  cleanupInterval?: number; // minutes
}

export interface UseDocumentUploadReturn {
  // Upload queue
  queueItems: UploadQueueItem[];
  stats: UploadStats;

  // Actions
  addToQueue: (files: File[]) => {
    success: string[];
    errors: FileValidationError[];
  };
  removeFromQueue: (fileId: string) => boolean;
  retryUpload: (fileId: string) => boolean;
  cancelAllUploads: () => void;
  cleanupCompleted: () => number;

  // Status
  isUploading: boolean;
  hasActiveUploads: boolean;
  allCompleted: boolean;
  hasErrors: boolean;

  // Progress
  overallProgress: number;
  uploadSpeed: string;
  estimatedTimeRemaining: string;

  // Validation
  validateFiles: (files: File[]) => {
    isValid: boolean;
    errors: FileValidationError[];
  };

  // Utility
  formatFileSize: (bytes: number) => string;
  formatTime: (seconds: number) => string;
  getStatusText: (status: UploadQueueItem['status']) => string;
  getFileIcon: (file: File) => string;
}

export const useDocumentUpload = (
  options: UseDocumentUploadOptions = {}
): UseDocumentUploadReturn => {
  const {
    maxConcurrentUploads = 3,
    maxFileSize = UPLOAD_LIMITS.MAX_FILE_SIZE_MB * 1024 * 1024,
    maxFiles = UPLOAD_LIMITS.MAX_FILES_PER_UPLOAD,
    allowedTypes = [...UPLOAD_LIMITS.SUPPORTED_FORMATS],
    currentQuotaUsed = 0,
    maxQuota = 5 * 1024 * 1024 * 1024, // 5GB
    autoCleanup = true,
    cleanupInterval = 30, // minutes
  } = options;

  const [queueItems, setQueueItems] = useState<UploadQueueItem[]>([]);
  const [stats, setStats] = useState<UploadStats>({
    totalFiles: 0,
    completedFiles: 0,
    failedFiles: 0,
    uploadingFiles: 0,
    processingFiles: 0,
    totalSize: 0,
    uploadedSize: 0,
    averageUploadSpeed: 0,
    estimatedTimeRemaining: 0,
  });

  const cleanupIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // WebSocket for real-time updates
  const { updates: processingUpdates } = useDocumentProcessingUpdates();

  // Subscribe to upload service progress
  useEffect(() => {
    const unsubscribeProgress = uploadService.onProgress((items) => {
      setQueueItems(items);
    });

    const unsubscribeStats = uploadService.onStatsUpdate((newStats) => {
      setStats(newStats);
    });

    return () => {
      unsubscribeProgress();
      unsubscribeStats();
    };
  }, []);

  // Handle WebSocket processing updates
  useEffect(() => {
    processingUpdates.forEach((update) => {
      const jobId = update.payload.job_id;
      const item = queueItems.find((item) => item.jobId === jobId);

      if (item) {
        // Update item with WebSocket data
        item.progress = update.payload.progress || item.progress;

        // Map document processing status to upload queue status
        if (update.payload.status === 'indexed') {
          item.status = 'completed';
          item.completedAt = Date.now();
          item.progress = 100;
        } else if (update.payload.status === 'failed') {
          item.status = 'error';
          item.error = update.payload.error_message || 'Processing failed';
        }
      }
    });
  }, [processingUpdates, queueItems]);

  // Auto-cleanup completed items
  useEffect(() => {
    if (autoCleanup) {
      cleanupIntervalRef.current = setInterval(
        () => {
          uploadService.cleanupCompleted(cleanupInterval);
        },
        cleanupInterval * 60 * 1000
      );

      return () => {
        if (cleanupIntervalRef.current) {
          clearInterval(cleanupIntervalRef.current);
        }
      };
    }
    return undefined;
  }, [autoCleanup, cleanupInterval]);

  // Add files to queue
  const addToQueue = useCallback(
    (files: File[]) => {
      // Validate files
      const validation = validateFileBatch(
        files,
        queueItems.length,
        currentQuotaUsed,
        {
          maxFileSize,
          maxFiles,
          allowedTypes,
          maxQuota,
        }
      );

      if (validation.isValid) {
        const fileIds = uploadService.addToQueue(files);
        return { success: fileIds, errors: [] };
      }

      // If validation failed, return only the errors
      return { success: [], errors: validation.errors };
    },
    [
      queueItems.length,
      currentQuotaUsed,
      maxFileSize,
      maxFiles,
      allowedTypes,
      maxQuota,
    ]
  );

  // Remove item from queue
  const removeFromQueue = useCallback((fileId: string) => {
    return uploadService.removeFromQueue(fileId);
  }, []);

  // Retry failed upload
  const retryUpload = useCallback((fileId: string) => {
    return uploadService.retryUpload(fileId);
  }, []);

  // Cancel all uploads
  const cancelAllUploads = useCallback(() => {
    uploadService.cancelAllUploads();
  }, []);

  // Cleanup completed items
  const cleanupCompleted = useCallback(() => {
    return uploadService.cleanupCompleted(0); // Clean all completed items
  }, []);

  // Validate files without adding to queue
  const validateFiles = useCallback(
    (files: File[]) => {
      return validateFileBatch(files, queueItems.length, currentQuotaUsed, {
        maxFileSize,
        maxFiles,
        allowedTypes,
        maxQuota,
      });
    },
    [
      queueItems.length,
      currentQuotaUsed,
      maxFileSize,
      maxFiles,
      allowedTypes,
      maxQuota,
    ]
  );

  // Calculate derived status
  const isUploading = stats.uploadingFiles > 0;
  const hasActiveUploads =
    stats.uploadingFiles > 0 || stats.processingFiles > 0;
  const allCompleted =
    stats.totalFiles > 0 &&
    stats.completedFiles + stats.failedFiles === stats.totalFiles;
  const hasErrors = stats.failedFiles > 0;

  // Calculate overall progress
  const overallProgress =
    stats.totalSize > 0
      ? Math.round((stats.uploadedSize / stats.totalSize) * 100)
      : 0;

  // Format upload speed
  const formatUploadSpeed = useCallback((bytesPerSecond: number): string => {
    if (bytesPerSecond === 0) return '0 B/s';

    const k = 1024;
    const sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
    const i = Math.floor(Math.log(bytesPerSecond) / Math.log(k));

    return `${(bytesPerSecond / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  }, []);

  // Format time remaining
  const formatTimeRemaining = useCallback((seconds: number): string => {
    if (seconds === 0 || !isFinite(seconds)) return 'Calculating...';

    if (seconds < 60) {
      return `${Math.ceil(seconds)}s`;
    } else if (seconds < 3600) {
      const minutes = Math.ceil(seconds / 60);
      return `${minutes}m`;
    } else {
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.ceil((seconds % 3600) / 60);
      return `${hours}h ${minutes}m`;
    }
  }, []);

  // Format file size
  const formatFileSize = useCallback((bytes: number): string => {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  }, []);

  // Format time duration
  const formatTime = useCallback((seconds: number): string => {
    if (seconds < 60) {
      return `${Math.round(seconds)}s`;
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60);
      const remainingSeconds = Math.round(seconds % 60);
      return `${minutes}m ${remainingSeconds}s`;
    } else {
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      return `${hours}h ${minutes}m`;
    }
  }, []);

  // Get status text
  const getStatusText = useCallback(
    (status: UploadQueueItem['status']): string => {
      switch (status) {
        case 'pending':
          return 'Waiting to upload';
        case 'uploading':
          return 'Uploading...';
        case 'processing':
          return 'Processing...';
        case 'completed':
          return 'Completed';
        case 'error':
          return 'Failed';
        default:
          return 'Unknown';
      }
    },
    []
  );

  // Get file icon
  const getFileIcon = useCallback((file: File): string => {
    const type = file.type ?? '';
    if (type === 'application/pdf') return 'pdf';
    if (type === 'text/plain') return 'text';
    if (type.startsWith('image/')) return 'image';
    if (type.startsWith('audio/')) return 'audio';
    if (type.startsWith('video/')) return 'video';
    return 'file';
  }, []);

  return {
    // Upload queue
    queueItems,
    stats,

    // Actions
    addToQueue,
    removeFromQueue,
    retryUpload,
    cancelAllUploads,
    cleanupCompleted,

    // Status
    isUploading,
    hasActiveUploads,
    allCompleted,
    hasErrors,

    // Progress
    overallProgress,
    uploadSpeed: formatUploadSpeed(stats.averageUploadSpeed),
    estimatedTimeRemaining: formatTimeRemaining(stats.estimatedTimeRemaining),

    // Validation
    validateFiles,

    // Utility
    formatFileSize,
    formatTime,
    getStatusText,
    getFileIcon,
  };
};

export default useDocumentUpload;
