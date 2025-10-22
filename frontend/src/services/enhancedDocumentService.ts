
/**
 * Enhanced Document Service
 * Integrates with the advanced document upload API with real-time progress tracking,
 * knowledge graph integration, and multimodal processing
 */

import { apiClient } from './apiClient';
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
  private readonly basePath = '/api/v2/documents/upload';
  private websocketConnections: Map<string, WebSocket> = new Map();

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
    if (request.description) formData.append('description', request.description);
    if (request.tags) formData.append('tags', request.tags.join(','));
    if (request.is_public !== undefined) formData.append('is_public', request.is_public.toString());
    if (request.processing_priority) formData.append('processing_priority', request.processing_priority);
    if (request.enable_quality_check !== undefined) formData.append('enable_quality_check', request.enable_quality_check.toString());
    if (request.custom_metadata) formData.append('custom_metadata', JSON.stringify(request.custom_metadata));

    // Make the upload request
    const response = await apiClient.post<DocumentUploadResponse>(`${this.basePath}/single`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    // Connect to WebSocket for progress updates
    const websocket = await this.connectProgressWebSocket(response.upload_id, onProgress);

    return {
      response: response,
      websocket
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
      const wsUrl = this.getWebSocketUrl(`/api/v2/documents/upload/progress/${uploadId}/ws`);
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
   */
  async getUploadProgress(uploadId: string): Promise<APIResponse<UploadProgressResponse>> {
    return apiClient.get(`${this.basePath}/progress/${uploadId}`);
  }

  /**
   * Cancel an ongoing upload
   */
  async cancelUpload(uploadId: string): Promise<APIResponse<{ message: string }>> {
    // Close WebSocket connection if exists
    const websocket = this.websocketConnections.get(uploadId);
    if (websocket) {
      websocket.close();
      this.websocketConnections.delete(uploadId);
    }

    return apiClient.delete(`${this.basePath}/cancel/${uploadId}`);
  }

  /**
   * Get comprehensive quality assessment for a document
   */
  async getDocumentQuality(documentId: string): Promise<APIResponse<QualityAssessmentResponse>> {
    return apiClient.get(`${this.basePath}/${documentId}/quality`);
  }

  /**
   * Rescan document for security threats
   */
  async rescanDocumentSecurity(documentId: string): Promise<APIResponse<{
    message: string;
    document_id: string;
    scan_result: SecurityScanResult;
    scanned_at: string;
  }>> {
    return apiClient.post(`${this.basePath}/${documentId}/rescan`);
  }

  /**
   * Get processing job status with detailed results
   */
  async getProcessingJobStatus(jobId: string): Promise<APIResponse<ProcessingJobStatus>> {
    return apiClient.get(`/api/v1/processing/jobs/${jobId}`);
  }

  /**
   * Get extracted entities and relationships for a document
   */
  async getDocumentEntities(documentId: string): Promise<APIResponse<EntityExtractionResult>> {
    return apiClient.get(`/api/v1/documents/${documentId}/entities`);
  }

  /**
   * Get document processing status with all job details
   */
  async getDocumentProcessingStatus(documentId: string): Promise<APIResponse<{
    document_id: string;
    status: string;
    progress_percentage: number;
    total_jobs: number;
    completed_jobs: number;
    failed_jobs: number;
    running_jobs: number;
    jobs: ProcessingJobStatus[];
  }>> {
    return apiClient.get(`/api/v1/documents/${documentId}/status`);
  }

  /**
   * Retry failed processing for a document
   */
  async retryDocumentProcessing(documentId: string): Promise<APIResponse<{ job_id: string }>> {
    return apiClient.post(`/api/v1/documents/${documentId}/retry-processing`);
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

    const response = await apiClient.post<{ responses: DocumentUploadResponse[] }>(`${this.basePath}/batch`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    // Connect to WebSocket for each upload
    const websockets: WebSocket[] = [];
    for (const uploadResponse of response.responses) {
      try {
        const websocket = await this.connectProgressWebSocket(uploadResponse.upload_id, onProgress);
        websockets.push(websocket);
      } catch (error) {
        console.error(`Failed to connect WebSocket for upload ${uploadResponse.upload_id}:`, error);
      }
    }

    return {
      responses: response.responses,
      websockets
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
      errors
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
      'application/pdf': 2.0,      // PDF requires OCR
      'image/jpeg': 1.5,           // Images require OCR
      'image/png': 1.5,
      'audio/mpeg': 3.0,           // Audio requires transcription
      'audio/wav': 3.0,
      'video/mp4': 5.0,            // Video requires frame extraction + audio transcription
      'video/quicktime': 5.0,
      'text/plain': 0.5,           // Text is fastest
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 1.0,
    };

    const multiplier = typeMultipliers[file.type as keyof typeof typeMultipliers] || 1.0;

    return Math.ceil((baseTime + sizeTime) * multiplier);
  }
}

// Create singleton instance
export const enhancedDocumentService = new EnhancedDocumentService();

// Export convenience functions
export const uploadDocument = enhancedDocumentService.uploadDocument.bind(enhancedDocumentService);
export const connectProgressWebSocket = enhancedDocumentService.connectProgressWebSocket.bind(enhancedDocumentService);
export const getUploadProgress = enhancedDocumentService.getUploadProgress.bind(enhancedDocumentService);
export const cancelUpload = enhancedDocumentService.cancelUpload.bind(enhancedDocumentService);
export const getDocumentQuality = enhancedDocumentService.getDocumentQuality.bind(enhancedDocumentService);
export const getDocumentProcessingStatus = enhancedDocumentService.getDocumentProcessingStatus.bind(enhancedDocumentService);