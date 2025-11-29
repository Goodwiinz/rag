// Upload-related types extending the base document types

export interface UploadMetadata {
  title?: string;
  description?: string;
  tags?: string[];
  custom_fields?: Record<string, string>;
  processing_options?: ProcessingOptions;
}

export interface ProcessingOptions {
  extract_entities?: boolean;
  generate_summary?: boolean;
  create_thumbnails?: boolean;
  ocr_enabled?: boolean;
  speech_to_text?: boolean;
  video_frame_extraction?: boolean;
  quality_threshold?: number;
}

export interface UploadSession {
  id: string;
  user_id: string;
  organization_id: string;
  created_at: string;
  updated_at: string;
  status: 'active' | 'completed' | 'failed' | 'cancelled';
  total_files: number;
  completed_files: number;
  failed_files: number;
  processing_files: number;
  total_size: number;
  uploaded_size: number;
  estimated_completion_time?: string;
  metadata: Record<string, any>;
}

export interface UploadJob {
  id: string;
  session_id?: string;
  document_id?: string;
  file_name: string;
  file_type: string;
  file_size: number;
  status: 'queued' | 'uploading' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  current_step: string;
  error_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  upload_speed?: number; // bytes per second
  processing_steps?: ProcessingStep[];
  quality_metrics?: QualityMetrics;
}

export interface ProcessingStep {
  step: 'validation' | 'upload' | 'extraction' | 'indexing' | 'quality_check' | 'completion';
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  progress: number;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  metadata?: Record<string, any>;
}

export interface QualityMetrics {
  overall_score: number; // 0-100
  text_extraction_quality?: number;
  image_quality?: number;
  audio_quality?: number;
  video_quality?: number;
  processing_recommendations?: string[];
  issues?: QualityIssue[];
}

export interface QualityIssue {
  type: 'low_resolution' | 'corrupted_file' | 'poor_ocr_quality' | 'missing_metadata' | 'processing_error';
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  recommendation: string;
}

export interface UploadConfiguration {
  max_file_size: number; // bytes
  max_files_per_batch: number;
  allowed_file_types: string[];
  concurrent_uploads: number;
  auto_retry_failed: boolean;
  max_retry_attempts: number;
  processing_priority: 'low' | 'normal' | 'high';
  notify_on_completion: boolean;
  cleanup_completed_after_days: number;
}

export interface UploadAnalytics {
  total_uploads: number;
  successful_uploads: number;
  failed_uploads: number;
  average_upload_time: number; // seconds
  average_processing_time: number; // seconds
  total_data_uploaded: number; // bytes
  most_common_file_types: Array<{
    type: string;
    count: number;
    percentage: number;
  }>;
  upload_trends: Array<{
    date: string;
    uploads: number;
    success_rate: number;
  }>;
  performance_metrics: {
    average_upload_speed: number; // bytes per second
    peak_upload_speed: number;
    server_response_time: number; // milliseconds
    error_rate: number; // percentage
  };
}

export interface UploadEvent {
  type: 'upload_started' | 'upload_progress' | 'upload_completed' | 'upload_failed' | 'processing_started' | 'processing_completed' | 'processing_failed';
  job_id: string;
  session_id?: string;
  timestamp: string;
  data: {
    progress?: number;
    current_step?: string;
    error_message?: string;
    processing_time?: number;
    file_size?: number;
    upload_speed?: number;
  };
}

export interface UploadFilter {
  status?: UploadJob['status'][];
  file_types?: string[];
  date_range?: {
    start: string;
    end: string;
  };
  size_range?: {
    min: number;
    max: number;
  };
  user_id?: string;
  session_id?: string;
  quality_score_range?: {
    min: number;
    max: number;
  };
}

export interface BatchUploadRequest {
  files: Array<{
    file: File;
    metadata?: UploadMetadata;
  }>;
  session_id?: string;
  configuration?: Partial<UploadConfiguration>;
}

// BatchUploadResponse is defined in uploadService.ts to avoid duplication

// WebSocket message types for real-time upload updates
export interface UploadWebSocketMessage {
  type: 'upload_progress' | 'processing_update' | 'job_completed' | 'job_failed' | 'session_completed';
  job_id?: string;
  session_id?: string;
  timestamp: string;
  payload: {
    progress?: number;
    status?: UploadJob['status'];
    current_step?: string;
    error_message?: string;
    processing_steps?: ProcessingStep[];
    quality_metrics?: QualityMetrics;
    document_id?: string;
  };
}

// Utility types for upload components
export interface UploadComponentState {
  files: File[];
  uploading: boolean;
  progress: number;
  error?: string;
  sessionId?: string;
  jobIds: string[];
}

export interface FileWithMetadata extends File {
  id: string;
  metadata?: UploadMetadata;
  preview?: string;
  uploadProgress?: number;
  processingProgress?: number;
  status?: 'pending' | 'uploading' | 'processing' | 'completed' | 'error';
  error?: string;
  jobId?: string;
  documentId?: string;
}

export type UploadValidationRule = {
  name: string;
  validator: (file: File) => boolean | Promise<boolean>;
  message: string;
  severity: 'warning' | 'error';
};

export interface UploadValidationResult {
  isValid: boolean;
  errors: Array<{
    file: File;
    rule: string;
    message: string;
  }>;
  warnings: Array<{
    file: File;
    rule: string;
    message: string;
  }>;
}

// Re-export from document types for convenience
export type { DocumentUpload, UploadProgress } from './document';