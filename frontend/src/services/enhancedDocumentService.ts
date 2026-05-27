/**
 * Enhanced Document Service
 * Integrates with the advanced document upload API with real-time progress tracking,
 * knowledge graph integration, and multimodal processing
 */

import { api } from '@/services/api-client';
import { APIResponse } from '@/types/api';

// Enhanced types for the new API
export interface DocumentUploadRequest {
  title: string;
  description?: string;
  tags?: string[];
  is_public?: boolean;
  processing_priority?: 'low' | 'normal' | 'high' | 'urgent';
  enable_quality_check?: boolean;
  custom_metadata?: Record<string, any>;
}

export interface DocumentUploadResponse {
  document_id: string;
  upload_id: string;
  title: string;
  filename: string;
  document_type: string;
  file_size_bytes: number;
  file_size_mb: number;
  mime_type: string;
  processing_status: string;
  job_id?: string;
  estimated_processing_time?: number;
  quality_score?: number;
  security_scan_result?: SecurityScanResult;
  upload_progress: number;
  message: string;
  created_at: string;
}

export interface SecurityScanResult {
  scan_status: 'passed' | 'failed' | 'warning';
  virus_detected: boolean;
  suspicious_content: boolean;
  file_integrity: string;
  scan_timestamp: string;
  threats: Array<{
    type: string;
    severity: 'low' | 'medium' | 'high' | 'critical';
    description: string;
  }>;
  warnings: string[];
}

export interface QualityAssessmentResponse {
  document_id: string;
  overall_score: number;
  readability_score: number;
  content_quality_score: number;
  technical_quality_score: number;
  recommendations: string[];
  issues: Array<{
    type: string;
    severity: 'low' | 'medium' | 'high';
    description: string;
    suggestion?: string;
  }>;
  processing_time_ms: number;
}

export interface UploadProgressResponse {
  upload_id: string;
  progress_percentage: number;
  current_step: string;
  total_steps: number;
  completed_steps: number;
  estimated_remaining_seconds?: number;
  error_message?: string;
}

export interface DocumentProcessingStatusResponse {
  document_id: string;
  processing_status: string;
  progress_percentage: number;
  current_step?: string;
  processing_started_at?: string;
  estimated_completion?: string;
  error_message?: string;
}

export interface ProcessingJobStatus {
  job_id: string;
  document_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress_percentage: number;
  current_step: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  result_data?: {
    extraction?: any;
    entities?: any;
    relationships?: any;
    knowledge_graph?: any;
    vectors?: any;
    total_processing_time_ms?: number;
  };
}

export interface EntityExtractionResult {
  document_id: string;
  entities: Array<{
    id: string;
    text: string;
    type: string;
    confidence: number;
    start_position?: number;
    end_position?: number;
    context?: string;
    neo4j_node_id?: string;
  }>;
  relationships: Array<{
    id: string;
    source_entity_id: string;
    target_entity_id: string;
    relationship_type: string;
    confidence: number;
    context?: string;
    neo4j_relationship_id?: string;
  }>;
  total_entities: number;
  total_relationships: number;
  processing_time_ms: number;
}

export interface WebSocketProgressUpdate {
  type: 'progress_update' | 'upload_complete' | 'error' | 'status_change';
  upload_id: string;
  progress_percentage?: number;
  current_step?: string;
  total_steps?: number;
  completed_steps?: number;
  estimated_remaining_seconds?: number;
  error_message?: string;
  result?: any;
  timestamp: string;
}

export class EnhancedDocumentService {
  private readonly basePath = '/api/v1/files'; // Using v1 API for now
  private websocketConnections: Map<string, WebSocket> = new Map();
  private statusPollers: Map<string, ReturnType<typeof setTimeout>> = new Map();
  private readonly statusPollIntervalMs = 2000;
  private readonly maxStatusPollAttempts = 60;

  /**
   * Upload a single document with enhanced processing
   */
  async uploadDocument(
    file: File,
    request: DocumentUploadRequest,
    onProgress?: (update: WebSocketProgressUpdate) => void
  ): Promise<{ response: DocumentUploadResponse; websocket: WebSocket }> {
    const formData = new FormData();

    // Add file
    formData.append('file', file);

    // Add form fields
    formData.append('title', request.title);
    if (request.description)
      formData.append('description', request.description);
    if (request.tags) formData.append('tags', request.tags.join(','));
    if (request.is_public !== undefined)
      formData.append('is_public', request.is_public.toString());

    // Ensure processing_priority is always sent (backend requires it)
    formData.append(
      'processing_priority',
      request.processing_priority || 'normal'
    );

    if (request.enable_quality_check !== undefined)
      formData.append(
        'enable_quality_check',
        request.enable_quality_check.toString()
      );
    if (request.custom_metadata)
      formData.append(
        'custom_metadata',
        JSON.stringify(request.custom_metadata)
      );

    // Make the upload request using the correct v1 endpoint
    // DON'T set Content-Type header manually - Axios will set it correctly for FormData
    const response = await api.post<DocumentUploadResponse>(
      '/files/upload',
      formData
    );

    // Note: WebSocket progress tracking not yet implemented in backend
    // Return null websocket for now
    // TODO: Implement WebSocket progress tracking when backend supports it

    if (onProgress) {
      if (this.isTerminalProcessingStatus(response.processing_status)) {
        onProgress({
          type:
            response.processing_status === 'failed'
              ? 'error'
              : 'upload_complete',
          upload_id: response.upload_id,
          error_message:
            response.processing_status === 'failed'
              ? response.message
              : undefined,
          result:
            response.processing_status === 'failed'
              ? undefined
              : {
                  document_id: response.document_id,
                  job_id: response.job_id,
                  title: response.title,
                  status: response.processing_status,
                },
          timestamp: new Date().toISOString(),
        });
      } else {
        void this.pollDocumentStatus(response, onProgress);
      }
    }

    return {
      response: response,
      websocket: null as any, // Placeholder until WebSocket is implemented
    };
  }

  /**
   * Connect to WebSocket for real-time progress updates
   */
  async connectProgressWebSocket(
    uploadId: string,
    onProgress?: (update: WebSocketProgressUpdate) => void
  ): Promise<WebSocket> {
    return new Promise((resolve, reject) => {
      const wsUrl = this.getWebSocketUrl(
        `/api/v2/documents/upload/progress/${uploadId}/ws`
      );
      const websocket = new WebSocket(wsUrl);

      websocket.onopen = () => {
        console.log(`Connected to progress WebSocket for upload ${uploadId}`);
        this.websocketConnections.set(uploadId, websocket);
        resolve(websocket);
      };

      websocket.onmessage = (event) => {
        try {
          const update: WebSocketProgressUpdate = JSON.parse(event.data);
          if (onProgress) {
            onProgress(update);
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.websocketConnections.delete(uploadId);
        reject(error);
      };

      websocket.onclose = () => {
        console.log(`WebSocket connection closed for upload ${uploadId}`);
        this.websocketConnections.delete(uploadId);
      };
    });
  }

  /**
   * Get upload progress via HTTP (fallback)
   * Note: v1 API doesn't have progress tracking, so we'll use the document status endpoint
   */
  async getUploadProgress(
    uploadId: string
  ): Promise<APIResponse<UploadProgressResponse>> {
    // For v1 API, we need to get document status instead of upload progress
    // This is a limitation of the v1 API
    return api.get(`/documents/status`);
  }

  /**
   * Cancel an ongoing upload
   */
  async cancelUpload(
    uploadId: string
  ): Promise<APIResponse<{ message: string }>> {
    this.clearStatusPolling(uploadId);

    // Close WebSocket connection if exists
    const websocket = this.websocketConnections.get(uploadId);
    if (websocket) {
      websocket.close();
      this.websocketConnections.delete(uploadId);
    }

    return api.delete(`/files/cancel/${uploadId}`);
  }

  /**
   * Get comprehensive quality assessment for a document
   */
  async getDocumentQuality(
    documentId: string
  ): Promise<APIResponse<QualityAssessmentResponse>> {
    return api.get(`${this.basePath}/${documentId}/quality`);
  }

  /**
   * Rescan document for security threats
   */
  async rescanDocumentSecurity(documentId: string): Promise<
    APIResponse<{
      message: string;
      document_id: string;
      scan_result: SecurityScanResult;
      scanned_at: string;
    }>
  > {
    return api.post(`${this.basePath}/${documentId}/rescan`);
  }

  /**
   * Get processing job status with detailed results
   */
  async getProcessingJobStatus(
    jobId: string
  ): Promise<APIResponse<ProcessingJobStatus>> {
    return api.get(`/processing/jobs/${jobId}`);
  }

  /**
   * Get extracted entities and relationships for a document
   */
  async getDocumentEntities(
    documentId: string
  ): Promise<APIResponse<EntityExtractionResult>> {
    return api.get(`/documents/${documentId}/entities`);
  }

  /**
   * Get document processing status with all job details
   */
  async getDocumentProcessingStatus(documentId: string): Promise<
    APIResponse<{
      document_id: string;
      status: string;
      progress_percentage: number;
      total_jobs: number;
      completed_jobs: number;
      failed_jobs: number;
      running_jobs: number;
      jobs: ProcessingJobStatus[];
    }>
  > {
    return api.get(`/documents/${documentId}/status`);
  }

  /**
   * Retry failed processing for a document
   */
  async retryDocumentProcessing(
    documentId: string
  ): Promise<APIResponse<{ job_id: string }>> {
    return api.post(`/documents/${documentId}/reprocess`);
  }

  /**
   * Batch upload multiple documents
   */
  async uploadBatchDocuments(
    files: File[],
    requests: DocumentUploadRequest[],
    onProgress?: (update: WebSocketProgressUpdate) => void
  ): Promise<{ responses: DocumentUploadResponse[]; websockets: WebSocket[] }> {
    const formData = new FormData();

    // Add files
    files.forEach((file) => {
      formData.append(`files`, file);
    });

    // Add metadata for each file
    formData.append('upload_requests', JSON.stringify(requests));

    const response = await api.post<{
      responses: DocumentUploadResponse[];
    }>(`${this.basePath}/batch`, formData);

    // Connect to WebSocket for each upload
    const websockets: WebSocket[] = [];
    for (const uploadResponse of response.responses) {
      try {
        const websocket = await this.connectProgressWebSocket(
          uploadResponse.upload_id,
          onProgress
        );
        websockets.push(websocket);
      } catch (error) {
        console.error(
          `Failed to connect WebSocket for upload ${uploadResponse.upload_id}:`,
          error
        );
      }
    }

    return {
      responses: response.responses,
      websockets,
    };
  }

  /**
   * Get WebSocket URL for progress updates
   */
  private getWebSocketUrl(path: string): string {
    const baseURL = 'http://localhost:8000';
    const wsProtocol = baseURL.startsWith('https://') ? 'wss://' : 'ws://';
    const wsBaseURL = baseURL.replace(/^https?:\/\//, wsProtocol);
    return `${wsBaseURL}${path}`;
  }

  /**
   * Close all WebSocket connections
   */
  closeAllConnections(): void {
    this.statusPollers.forEach((poller) => {
      clearTimeout(poller);
    });
    this.statusPollers.clear();

    this.websocketConnections.forEach((websocket, uploadId) => {
      websocket.close();
      console.log(`Closed WebSocket connection for upload ${uploadId}`);
    });
    this.websocketConnections.clear();
  }

  /**
   * Check if file type is supported
   */
  isSupportedFileType(file: File): boolean {
    const supportedTypes = {
      'application/pdf': true,
      'text/plain': true,
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': true,
      'image/jpeg': true,
      'image/png': true,
      'audio/mpeg': true,
      'audio/wav': true,
      'video/mp4': true,
      'video/quicktime': true,
    };

    return supportedTypes[file.type as keyof typeof supportedTypes] || false;
  }

  /**
   * Validate file before upload
   */
  validateFile(file: File): { isValid: boolean; errors: string[] } {
    const errors: string[] = [];

    // Check file type
    if (!this.isSupportedFileType(file)) {
      errors.push(`Unsupported file type: ${file.type}`);
    }

    // Check file size (50MB limit)
    const maxSize = 50 * 1024 * 1024; // 50MB
    if (file.size > maxSize) {
      errors.push(`File size exceeds 50MB limit`);
    }

    // Check filename
    if (!file.name || file.name.length > 255) {
      errors.push('Invalid filename');
    }

    return {
      isValid: errors.length === 0,
      errors,
    };
  }

  /**
   * Get estimated processing time for a file
   */
  estimateProcessingTime(file: File): number {
    // Base processing time in seconds
    const baseTime = 30;

    // Add time based on file size (1 second per MB)
    const sizeTime = (file.size / (1024 * 1024)) * 1;

    // Add time based on file type
    const typeMultipliers = {
      'application/pdf': 2.0, // PDF requires OCR
      'image/jpeg': 1.5, // Images require OCR
      'image/png': 1.5,
      'audio/mpeg': 3.0, // Audio requires transcription
      'audio/wav': 3.0,
      'video/mp4': 5.0, // Video requires frame extraction + audio transcription
      'video/quicktime': 5.0,
      'text/plain': 0.5, // Text is fastest
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 1.0,
    };

    const multiplier =
      typeMultipliers[file.type as keyof typeof typeMultipliers] || 1.0;

    return Math.ceil((baseTime + sizeTime) * multiplier);
  }

  private async pollDocumentStatus(
    response: DocumentUploadResponse,
    onProgress: (update: WebSocketProgressUpdate) => void,
    attempt: number = 0
  ): Promise<void> {
    if (attempt >= this.maxStatusPollAttempts) {
      this.clearStatusPolling(response.upload_id);
      onProgress({
        type: 'error',
        upload_id: response.upload_id,
        error_message: 'Timed out waiting for document processing to complete',
        timestamp: new Date().toISOString(),
      });
      return;
    }

    try {
      const status = await api.get<DocumentProcessingStatusResponse>(
        `/documents/${response.document_id}/status`
      );

      onProgress({
        type: 'progress_update',
        upload_id: response.upload_id,
        progress_percentage: status.progress_percentage,
        current_step:
          status.current_step ||
          this.getFallbackStepLabel(status.processing_status),
        error_message: status.error_message,
        timestamp: new Date().toISOString(),
      });

      if (status.processing_status === 'failed') {
        this.clearStatusPolling(response.upload_id);
        onProgress({
          type: 'error',
          upload_id: response.upload_id,
          error_message: status.error_message || 'Document processing failed',
          timestamp: new Date().toISOString(),
        });
        return;
      }

      if (this.isCompletedProcessingStatus(status.processing_status)) {
        this.clearStatusPolling(response.upload_id);
        onProgress({
          type: 'upload_complete',
          upload_id: response.upload_id,
          result: {
            document_id: response.document_id,
            job_id: response.job_id,
            title: response.title,
            status: status.processing_status,
          },
          timestamp: new Date().toISOString(),
        });
        return;
      }

      this.scheduleStatusPolling(response, onProgress, attempt + 1);
    } catch (error) {
      console.error(
        `Failed to poll document status for ${response.document_id}:`,
        error
      );
      this.scheduleStatusPolling(response, onProgress, attempt + 1);
    }
  }

  private scheduleStatusPolling(
    response: DocumentUploadResponse,
    onProgress: (update: WebSocketProgressUpdate) => void,
    attempt: number
  ): void {
    this.clearStatusPolling(response.upload_id);

    const poller = setTimeout(() => {
      void this.pollDocumentStatus(response, onProgress, attempt);
    }, this.statusPollIntervalMs);

    this.statusPollers.set(response.upload_id, poller);
  }

  private clearStatusPolling(uploadId: string): void {
    const poller = this.statusPollers.get(uploadId);
    if (!poller) {
      return;
    }

    clearTimeout(poller);
    this.statusPollers.delete(uploadId);
  }

  private isCompletedProcessingStatus(status?: string): boolean {
    return status === 'indexed' || status === 'completed';
  }

  private isTerminalProcessingStatus(status?: string): boolean {
    return this.isCompletedProcessingStatus(status) || status === 'failed';
  }

  private getFallbackStepLabel(status?: string): string {
    switch (status) {
      case 'queued':
      case 'pending':
        return 'Queued for processing';
      case 'processing':
        return 'Processing';
      case 'indexed':
      case 'completed':
        return 'Completed';
      case 'failed':
        return 'Failed';
      default:
        return 'Processing';
    }
  }
}

// Create singleton instance
export const enhancedDocumentService = new EnhancedDocumentService();

// Export convenience functions
export const uploadDocument = enhancedDocumentService.uploadDocument.bind(
  enhancedDocumentService
);
export const connectProgressWebSocket =
  enhancedDocumentService.connectProgressWebSocket.bind(
    enhancedDocumentService
  );
export const getUploadProgress = enhancedDocumentService.getUploadProgress.bind(
  enhancedDocumentService
);
export const cancelUpload = enhancedDocumentService.cancelUpload.bind(
  enhancedDocumentService
);
export const getDocumentQuality =
  enhancedDocumentService.getDocumentQuality.bind(enhancedDocumentService);
export const getDocumentProcessingStatus =
  enhancedDocumentService.getDocumentProcessingStatus.bind(
    enhancedDocumentService
  );
