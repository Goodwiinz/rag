// Document Management Types
export interface Document {
  id: string;
  user_id: string;
  organization_id: string;
  title: string;
  filename: string;
  // Support both frontend naming (file_type) and backend naming (document_type)
  file_type?: 'pdf' | 'txt' | 'jpg' | 'png' | 'mp3' | 'mp4';
  document_type?: string; // Backend field name
  // Support both frontend naming (file_size) and backend naming (file_size_bytes)
  file_size?: number; // bytes - legacy frontend field
  file_size_bytes?: number; // Backend field name
  file_size_mb?: number; // Backend field name
  processing_status: 'queued' | 'processing' | 'indexed' | 'failed' | 'pending' | 'completed';
  processing_error?: string;
  // Support both frontend naming (upload_timestamp) and backend naming (created_at)
  upload_timestamp?: string; // Legacy frontend field
  created_at?: string; // Backend field name
  updated_at?: string; // Backend field name
  processing_started_at?: string;
  processing_completed_at?: string;
  thumbnail_url?: string;
  page_count?: number;
  duration_seconds?: number;
  extracted_text_preview?: string;
  content_preview?: string; // Backend field name
  content_summary?: string; // Backend field name
  metadata: Record<string, any>;
  description?: string;
  tags?: string[];
  custom_fields?: Record<string, any>;
  mime_type?: string;
  is_public?: boolean;
  uploaded_by_user_id?: string;
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
