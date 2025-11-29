import { apiClient } from './api';
import { DocumentUpload, UploadProgress } from '@/types';

export interface UploadResponse {
  job_id: string;
  message: string;
  estimated_processing_time_seconds: number;
  file_info: {
    id: string;
    filename: string;
    file_type: string;
    file_size: number;
    upload_timestamp: string;
  };
}

export interface BatchUploadResponse {
  jobs: Array<{
    job_id: string;
    file_info: UploadResponse['file_info'];
  }>;
  total_files: number;
  message: string;
  estimated_total_processing_time_seconds: number;
}

export interface UploadQueueItem {
  id: string;
  file: File;
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'error';
  progress: number;
  jobId?: string;
  documentId?: string;
  error?: string;
  uploadStartTime?: number;
  processingStartTime?: number;
  completedAt?: number;
  uploadResponse?: UploadResponse;
}

export interface UploadStats {
  totalFiles: number;
  completedFiles: number;
  failedFiles: number;
  uploadingFiles: number;
  processingFiles: number;
  totalSize: number;
  uploadedSize: number;
  averageUploadSpeed: number; // bytes per second
  estimatedTimeRemaining: number; // seconds
}

class UploadService {
  private uploadQueue: Map<string, UploadQueueItem> = new Map();
  private uploadControllers: Map<string, AbortController> = new Map();
  private progressCallbacks: Set<(items: UploadQueueItem[]) => void> = new Set();
  private statsCallbacks: Set<(stats: UploadStats) => void> = new Set();
  private activeUploads: Set<string> = new Set();
  private maxConcurrentUploads = 3;

  constructor() {
    // Start processing queue
    this.processQueue();
  }

  /**
   * Subscribe to upload progress updates
   */
  public onProgress(callback: (items: UploadQueueItem[]) => void): () => void {
    this.progressCallbacks.add(callback);
    return () => this.progressCallbacks.delete(callback);
  }

  /**
   * Subscribe to upload statistics updates
   */
  public onStatsUpdate(callback: (stats: UploadStats) => void): () => void {
    this.statsCallbacks.add(callback);
    return () => this.statsCallbacks.delete(callback);
  }

  /**
   * Notify all subscribers of progress updates
   */
  private notifyProgress(): void {
    const items = Array.from(this.uploadQueue.values());
    this.progressCallbacks.forEach(callback => callback(items));
    this.updateStats();
  }

  /**
   * Calculate and notify statistics
   */
  private updateStats(): void {
    const items = Array.from(this.uploadQueue.values());
    const stats: UploadStats = {
      totalFiles: items.length,
      completedFiles: items.filter(item => item.status === 'completed').length,
      failedFiles: items.filter(item => item.status === 'error').length,
      uploadingFiles: items.filter(item => item.status === 'uploading').length,
      processingFiles: items.filter(item => item.status === 'processing').length,
      totalSize: items.reduce((sum, item) => sum + item.file.size, 0),
      uploadedSize: items.reduce((sum, item) => {
        if (item.completedAt) return sum + item.file.size;
        if (item.uploadStartTime && item.progress > 0) {
          return sum + (item.file.size * item.progress / 100);
        }
        return sum;
      }, 0),
      averageUploadSpeed: this.calculateAverageUploadSpeed(items),
      estimatedTimeRemaining: this.calculateEstimatedTimeRemaining(items),
    };

    this.statsCallbacks.forEach(callback => callback(stats));
  }

  /**
   * Calculate average upload speed
   */
  private calculateAverageUploadSpeed(items: UploadQueueItem[]): number {
    const uploadingItems = items.filter(item =>
      item.status === 'uploading' && item.uploadStartTime
    );

    if (uploadingItems.length === 0) return 0;

    const totalSpeed = uploadingItems.reduce((sum, item) => {
      if (!item.uploadStartTime) return 0;
      const elapsedTime = (Date.now() - item.uploadStartTime) / 1000;
      const uploadedBytes = item.file.size * (item.progress / 100);
      return sum + (uploadedBytes / elapsedTime);
    }, 0);

    return totalSpeed / uploadingItems.length;
  }

  /**
   * Calculate estimated time remaining
   */
  private calculateEstimatedTimeRemaining(items: UploadQueueItem[]): number {
    const pendingItems = items.filter(item =>
      ['pending', 'uploading'].includes(item.status)
    );

    if (pendingItems.length === 0) return 0;

    const avgSpeed = this.calculateAverageUploadSpeed(items);
    if (avgSpeed === 0) return 0;

    const remainingBytes = pendingItems.reduce((sum, item) => {
      const remainingBytes = item.file.size * (1 - item.progress / 100);
      return sum + remainingBytes;
    }, 0);

    return Math.ceil(remainingBytes / avgSpeed);
  }

  /**
   * Add files to upload queue
   */
  public addToQueue(files: File[]): string[] {
    const fileIds: string[] = [];

    files.forEach(file => {
      const id = this.generateUploadId(file);
      const uploadItem: UploadQueueItem = {
        id,
        file,
        status: 'pending',
        progress: 0,
      };

      this.uploadQueue.set(id, uploadItem);
      fileIds.push(id);
    });

    this.notifyProgress();
    this.processQueue();

    return fileIds;
  }

  /**
   * Remove item from queue
   */
  public removeFromQueue(fileId: string): boolean {
    const item = this.uploadQueue.get(fileId);
    if (!item) return false;

    // Cancel upload if in progress
    if (item.status === 'uploading') {
      const controller = this.uploadControllers.get(fileId);
      if (controller) {
        controller.abort();
        this.uploadControllers.delete(fileId);
      }
      this.activeUploads.delete(fileId);
    }

    this.uploadQueue.delete(fileId);
    this.notifyProgress();
    return true;
  }

  /**
   * Retry failed upload
   */
  public retryUpload(fileId: string): boolean {
    const item = this.uploadQueue.get(fileId);
    if (!item || item.status !== 'error') return false;

    // Reset item state
    item.status = 'pending';
    item.progress = 0;
    item.error = undefined;
    item.jobId = undefined;
    item.documentId = undefined;
    item.uploadStartTime = undefined;
    item.processingStartTime = undefined;
    item.completedAt = undefined;
    item.uploadResponse = undefined;

    this.notifyProgress();
    this.processQueue();

    return true;
  }

  /**
   * Cancel all uploads
   */
  public cancelAllUploads(): void {
    // Abort all active uploads
    this.uploadControllers.forEach(controller => {
      controller.abort();
    });
    this.uploadControllers.clear();
    this.activeUploads.clear();

    // Clear queue
    this.uploadQueue.clear();
    this.notifyProgress();
  }

  /**
   * Get current queue items
   */
  public getQueueItems(): UploadQueueItem[] {
    return Array.from(this.uploadQueue.values());
  }

  /**
   * Get upload statistics
   */
  public getStats(): UploadStats {
    const items = Array.from(this.uploadQueue.values());
    return {
      totalFiles: items.length,
      completedFiles: items.filter(item => item.status === 'completed').length,
      failedFiles: items.filter(item => item.status === 'error').length,
      uploadingFiles: items.filter(item => item.status === 'uploading').length,
      processingFiles: items.filter(item => item.status === 'processing').length,
      totalSize: items.reduce((sum, item) => sum + item.file.size, 0),
      uploadedSize: items.reduce((sum, item) => {
        if (item.completedAt) return sum + item.file.size;
        if (item.uploadStartTime && item.progress > 0) {
          return sum + (item.file.size * item.progress / 100);
        }
        return sum;
      }, 0),
      averageUploadSpeed: this.calculateAverageUploadSpeed(items),
      estimatedTimeRemaining: this.calculateEstimatedTimeRemaining(items),
    };
  }

  /**
   * Process upload queue
   */
  private async processQueue(): Promise<void> {
    while (this.activeUploads.size < this.maxConcurrentUploads) {
      const nextItem = this.getNextPendingItem();
      if (!nextItem) break;

      this.activeUploads.add(nextItem.id);
      this.uploadFile(nextItem).finally(() => {
        this.activeUploads.delete(nextItem.id);
        // Process next item in queue
        setTimeout(() => this.processQueue(), 100);
      });
    }
  }

  /**
   * Get next pending item from queue
   */
  private getNextPendingItem(): UploadQueueItem | null {
    for (const item of this.uploadQueue.values()) {
      if (item.status === 'pending') {
        return item;
      }
    }
    return null;
  }

  /**
   * Upload individual file
   */
  private async uploadFile(item: UploadQueueItem): Promise<void> {
    try {
      // Update status to uploading
      item.status = 'uploading';
      item.uploadStartTime = Date.now();
      this.notifyProgress();

      // Create abort controller
      const controller = new AbortController();
      this.uploadControllers.set(item.id, controller);

      // Prepare form data
      const formData = new FormData();
      formData.append('file', item.file);

      // Create upload request with progress tracking
      const response = await this.uploadWithProgress(
        '/files/upload',
        formData,
        controller.signal,
        (progress) => {
          item.progress = progress;
          this.notifyProgress();
        }
      );

      // Store upload response
      item.uploadResponse = response;
      item.jobId = response.job_id;
      item.documentId = response.file_info.id;
      item.status = 'processing';
      item.processingStartTime = Date.now();
      item.progress = 0; // Reset for processing progress
      this.notifyProgress();

      // Start polling for processing status
      this.pollProcessingStatus(item);

    } catch (error) {
      console.error('Upload failed for file:', item.file.name, error);

      item.status = 'error';
      item.error = error instanceof Error ? error.message : 'Upload failed';
      this.notifyProgress();
    } finally {
      // Clean up controller
      this.uploadControllers.delete(item.id);
    }
  }

  /**
   * Upload file with progress tracking
   */
  private async uploadWithProgress(
    endpoint: string,
    formData: FormData,
    signal: AbortSignal,
    onProgress: (progress: number) => void
  ): Promise<UploadResponse> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      // Progress tracking
      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          const progress = (event.loaded / event.total) * 100;
          onProgress(Math.round(progress));
        }
      });

      // Load completion
      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText);
            resolve(response);
          } catch (error) {
            reject(new Error('Invalid response format'));
          }
        } else {
          try {
            const errorResponse = JSON.parse(xhr.responseText);
            reject(new Error(errorResponse.error?.message || `Upload failed: ${xhr.statusText}`));
          } catch {
            reject(new Error(`Upload failed: ${xhr.statusText}`));
          }
        }
      });

      // Error handling
      xhr.addEventListener('error', () => {
        reject(new Error('Network error during upload'));
      });

      xhr.addEventListener('abort', () => {
        reject(new Error('Upload cancelled'));
      });

      // Open and send request
      xhr.open('POST', `${apiClient['baseURL']}${endpoint}`);

      // Add auth headers
      const authHeaders = apiClient['token'] && apiClient['organizationId']
        ? { Authorization: `Bearer ${apiClient['token']}`, 'X-Organization-ID': apiClient['organizationId'] }
        : {};

      Object.entries(authHeaders).forEach(([key, value]) => {
        xhr.setRequestHeader(key, value);
      });

      // Send request with signal
      signal.addEventListener('abort', () => {
        xhr.abort();
      });

      xhr.send(formData);
    });
  }

  /**
   * Poll processing status
   */
  private async pollProcessingStatus(item: UploadQueueItem): Promise<void> {
    const pollInterval = 2000; // 2 seconds
    let attempts = 0;
    const maxAttempts = 600; // 20 minutes max

    const poll = async () => {
      try {
        if (attempts >= maxAttempts) {
          item.status = 'error';
          item.error = 'Processing timeout';
          this.notifyProgress();
          return;
        }

        const status = await apiClient.getJobStatus(item.jobId!);

        item.progress = status.progress;

        if (status.status === 'completed') {
          item.status = 'completed';
          item.completedAt = Date.now();
          item.progress = 100;
          this.notifyProgress();
          return;
        }

        if (status.status === 'failed') {
          item.status = 'error';
          item.error = status.error_message || 'Processing failed';
          this.notifyProgress();
          return;
        }

        // Continue polling
        attempts++;
        setTimeout(poll, pollInterval);

      } catch (error) {
        console.error('Error polling processing status:', error);
        attempts++;
        setTimeout(poll, pollInterval);
      }
    };

    poll();
  }

  /**
   * Generate unique upload ID
   */
  private generateUploadId(file: File): string {
    const timestamp = Date.now().toString(36);
    const randomString = Math.random().toString(36).substr(2, 9);
    const fileHash = file.name + file.size + file.type;
    const fileHashShort = fileHash.split('').reduce((acc, char) => {
      return ((acc << 5) - acc + char.charCodeAt(0)) & 0xffffffff;
    }, 0).toString(36);

    return `upload_${timestamp}_${randomString}_${fileHashShort}`;
  }

  /**
   * Clean up completed items from queue
   */
  public cleanupCompleted(olderThanMinutes: number = 30): number {
    const cutoffTime = Date.now() - (olderThanMinutes * 60 * 1000);
    let removedCount = 0;

    for (const [id, item] of this.uploadQueue.entries()) {
      if (
        (item.status === 'completed' || item.status === 'error') &&
        item.completedAt &&
        item.completedAt < cutoffTime
      ) {
        this.uploadQueue.delete(id);
        removedCount++;
      }
    }

    if (removedCount > 0) {
      this.notifyProgress();
    }

    return removedCount;
  }
}

// Create and export singleton instance
export const uploadService = new UploadService();

export default uploadService;