/**
 * Enhanced Document Service with Type Safety
 * Provides type-safe document upload and processing with runtime validation
 */

import { typeSafeApiClient } from './typeSafeApiClient';
import * as schemas from '@/types/schemas';
import { validateFile, isSupportedFileType, type FileValidationResult } from '@/lib/typeGuards';
import { z } from 'zod';

// ============================================================================
// Enhanced Request/Response Types
// ============================================================================

export interface DocumentUploadRequest {
  title: string;
  description?: string;
  tags?: string[];
  is_public?: boolean;
  processing_priority?: 'low' | 'normal' | 'high' | 'urgent';
  enable_quality_check?: boolean;
  custom_metadata?: Record<string, any>;
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

// ============================================================================
// Zod Schemas for Enhanced Types
// ============================================================================

const SecurityScanResultSchema = z.object({
  scan_status: z.enum(['passed', 'failed', 'warning']),
  virus_detected: z.boolean(),
  suspicious_content: z.boolean(),
  file_integrity: z.string(),
  scan_timestamp: z.string(),
  threats: z.array(
    z.object({
      type: z.string(),
      severity: z.enum(['low', 'medium', 'high', 'critical']),
      description: z.string(),
    })
  ),
  warnings: z.array(z.string()),
});

const QualityAssessmentSchema = z.object({
  document_id: z.string().uuid(),
  overall_score: z.number().min(0).max(100),
  readability_score: z.number().min(0).max(100),
  content_quality_score: z.number().min(0).max(100),
  technical_quality_score: z.number().min(0).max(100),
  recommendations: z.array(z.string()),
  issues: z.array(
    z.object({
      type: z.string(),
      severity: z.enum(['low', 'medium', 'high']),
      description: z.string(),
      suggestion: z.string().optional(),
    })
  ),
  processing_time_ms: z.number().nonnegative(),
});

// ============================================================================
// Enhanced Document Service
// ============================================================================

export class EnhancedDocumentServiceV2 {
  private readonly basePath = '/api/v1/files';
  private websocketConnections: Map<string, WebSocket> = new Map();

  /**
   * Upload a single document with validation and type safety
   */
  async uploadDocument(
    file: File,
    request?: DocumentUploadRequest,
    onProgress?: (progress: number) => void
  ): Promise<schemas.DocumentUploadResponse> {
    // Validate file before upload
    const validation = validateFile(file);
    if (!validation.isValid) {
      throw new Error(`File validation failed: ${validation.errors.join(', ')}`);
    }

    // Log warnings if any
    if (validation.warnings.length > 0) {
      console.warn('File upload warnings:', validation.warnings);
    }

    const formData = new FormData();
    formData.append('file', file);

    // Add optional fields
    if (request?.title) formData.append('title', request.title);
    if (request?.description) formData.append('description', request.description);
    if (request?.tags) formData.append('tags', request.tags.join(','));
    if (request?.is_public !== undefined)
      formData.append('is_public', request.is_public.toString());
    if (request?.processing_priority)
      formData.append('processing_priority', request.processing_priority);
    if (request?.enable_quality_check !== undefined)
      formData.append('enable_quality_check', request.enable_quality_check.toString());
    if (request?.custom_metadata)
      formData.append('custom_metadata', JSON.stringify(request.custom_metadata));

    // Use type-safe client for upload
    const response = await typeSafeApiClient.uploadDocument(file);

    return response;
  }

  /**
   * Upload multiple documents in batch
   */
  async uploadBatchDocuments(
    files: File[],
    requests?: DocumentUploadRequest[],
    onProgress?: (uploadId: string, progress: number) => void
  ): Promise<schemas.DocumentUploadResponse[]> {
    // Validate all files first
    const validations = files.map((file) => validateFile(file));
    const invalidFiles = validations.filter((v) => !v.isValid);

    if (invalidFiles.length > 0) {
      const errors = invalidFiles.flatMap((v) => v.errors);
      throw new Error(`Batch validation failed: ${errors.join(', ')}`);
    }

    // Upload files sequentially (could be parallelized with Promise.all)
    const responses: schemas.DocumentUploadResponse[] = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const request = requests?.[i];

      try {
        const response = await this.uploadDocument(file, request);
        responses.push(response);

        if (onProgress) {
          onProgress(response.upload_id, ((i + 1) / files.length) * 100);
        }
      } catch (error) {
        console.error(`Failed to upload file ${file.name}:`, error);
        throw error;
      }
    }

    return responses;
  }

  /**
   * Get upload progress
   */
  async getUploadProgress(uploadId: string): Promise<schemas.UploadProgress> {
    return typeSafeApiClient.get(
      `${this.basePath}/progress/${uploadId}`,
      schemas.UploadProgressSchema
    );
  }

  /**
   * Get job status
   */
  async getJobStatus(jobId: string): Promise<schemas.UploadProgress> {
    return typeSafeApiClient.getJobStatus(jobId);
  }

  /**
   * Cancel an upload
   */
  async cancelUpload(uploadId: string): Promise<{ message: string }> {
    // Close WebSocket if exists
    const ws = this.websocketConnections.get(uploadId);
    if (ws) {
      ws.close();
      this.websocketConnections.delete(uploadId);
    }

    return typeSafeApiClient.delete(
      `${this.basePath}/cancel/${uploadId}`,
      z.object({ message: z.string() })
    );
  }

  /**
   * Get document quality assessment
   */
  async getDocumentQuality(documentId: string): Promise<QualityAssessmentResponse> {
    return typeSafeApiClient.get(
      `${this.basePath}/${documentId}/quality`,
      QualityAssessmentSchema
    );
  }

  /**
   * Rescan document for security
   */
  async rescanDocumentSecurity(documentId: string): Promise<{
    message: string;
    document_id: string;
    scan_result: SecurityScanResult;
    scanned_at: string;
  }> {
    return typeSafeApiClient.post(
      `${this.basePath}/${documentId}/rescan`,
      z.object({
        message: z.string(),
        document_id: z.string().uuid(),
        scan_result: SecurityScanResultSchema,
        scanned_at: z.string(),
      })
    );
  }

  /**
   * Retry failed document processing
   */
  async retryDocumentProcessing(documentId: string): Promise<{ job_id: string }> {
    return typeSafeApiClient.post(
      `/api/v1/documents/${documentId}/retry-processing`,
      z.object({ job_id: z.string().uuid() })
    );
  }

  /**
   * WebSocket connection for real-time progress (placeholder)
   * TODO: Implement when backend supports WebSocket
   */
  async connectProgressWebSocket(
    uploadId: string,
    onProgress?: (update: WebSocketProgressUpdate) => void
  ): Promise<WebSocket | null> {
    console.warn('WebSocket progress tracking not yet implemented in backend');
    return null;
  }

  /**
   * Validate file before upload
   */
  validateFile(file: File, maxSizeBytes?: number): FileValidationResult {
    return validateFile(file, maxSizeBytes);
  }

  /**
   * Check if file type is supported
   */
  isSupportedFileType(file: File): boolean {
    return isSupportedFileType(file.type);
  }

  /**
   * Estimate processing time based on file characteristics
   */
  estimateProcessingTime(file: File): number {
    const baseTime = 30; // seconds
    const sizeTime = (file.size / (1024 * 1024)) * 1; // 1 second per MB

    const typeMultipliers: Record<string, number> = {
      'application/pdf': 2.0,
      'image/jpeg': 1.5,
      'image/png': 1.5,
      'audio/mpeg': 3.0,
      'audio/wav': 3.0,
      'video/mp4': 5.0,
      'video/quicktime': 5.0,
      'text/plain': 0.5,
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 1.0,
    };

    const multiplier = typeMultipliers[file.type] || 1.0;
    return Math.ceil((baseTime + sizeTime) * multiplier);
  }

  /**
   * Get file category from MIME type
   */
  getFileCategory(file: File): 'document' | 'image' | 'audio' | 'video' | 'unknown' {
    if (file.type.startsWith('application/') || file.type.startsWith('text/')) {
      return 'document';
    }
    if (file.type.startsWith('image/')) {
      return 'image';
    }
    if (file.type.startsWith('audio/')) {
      return 'audio';
    }
    if (file.type.startsWith('video/')) {
      return 'video';
    }
    return 'unknown';
  }

  /**
   * Close all WebSocket connections
   */
  closeAllConnections(): void {
    this.websocketConnections.forEach((ws, uploadId) => {
      ws.close();
      console.log(`Closed WebSocket connection for upload ${uploadId}`);
    });
    this.websocketConnections.clear();
  }
}

// ============================================================================
// Singleton Instance
// ============================================================================

export const enhancedDocumentServiceV2 = new EnhancedDocumentServiceV2();

export default enhancedDocumentServiceV2;
