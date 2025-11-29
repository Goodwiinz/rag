// Document Management Types
export interface Document {
  id: string;
  user_id: string;
  organization_id: string;
  title: string;
  filename: string;
  file_type: 'pdf' | 'txt' | 'jpg' | 'png' | 'mp3' | 'mp4';
  file_size: number; // bytes
  processing_status: 'queued' | 'processing' | 'indexed' | 'failed';
  processing_error?: string;
  upload_timestamp: string;
  processing_completed_at?: string;
  thumbnail_url?: string;
  page_count?: number;
  duration_seconds?: number;
  extracted_text_preview?: string;
  metadata: Record<string, any>;
  description?: string;
  tags?: string[];
  custom_fields?: Record<string, any>;
}

export interface DocumentUpload {
  file: File;
  id: string;
  progress: number; // 0-100
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'error';
  error?: string;
  jobId?: string;
  documentId?: string;
}

export interface DocumentListResponse {
  documents: Document[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages?: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

export interface DocumentFilters {
  file_types?: Document['file_type'][];
  status?: Document['processing_status'][];
  date_range?: {
    start: string;
    end: string;
  };
  search_term?: string;
}

export interface UploadProgress {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress: number; // 0-100
  current_step: string;
  estimated_remaining_seconds?: number;
  error_message?: string;
}

