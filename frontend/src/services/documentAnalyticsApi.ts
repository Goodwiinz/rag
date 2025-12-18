/**
 * Document Analytics API Service
 * Provides methods for fetching document statistics, file type distributions,
 * processing status, and paginated document lists from the backend.
 */

import apiClient from './apiClient';

// Response Types
export interface FileTypeStats {
  type: string;
  count: number;
  total_size_mb: number;
}

export interface ProcessingStats {
  status: string;
  count: number;
}

export interface FileStatsResponse {
  files_by_type: FileTypeStats[];
  processing_stats: ProcessingStats[];
}

export interface DocumentResponse {
  id: string;
  title: string;
  filename: string;
  document_type: string;
  file_size_bytes: number;
  file_size_mb: number;
  mime_type: string;
  processing_status: string;
  tags: string[];
  is_public: boolean;
  content_preview?: string;
  created_at: string;
  updated_at: string;
  uploaded_by_user_id: string;
  organization_id: string;
}

export interface PaginationInfo {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface DocumentListResponse {
  documents: DocumentResponse[];
  pagination: PaginationInfo;
}

export interface DocumentAnalytics {
  total_documents: number;
  total_storage_mb: number;
  documents_by_type: Record<string, number>;
  processing_status_counts: Record<string, number>;
  average_file_size_mb: number;
  recent_uploads_count: number;
}

export interface DocumentStatusResponse {
  document_id: string;
  processing_status: string;
  progress_percentage: number;
  current_step?: string;
  processing_started_at?: string;
  estimated_completion?: string;
  error_message?: string;
}

// Query parameters
export interface DocumentListParams {
  page?: number;
  size?: number;
  status?: string;
  document_type?: string;
  search?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  tags?: string[];
}

/**
 * Document Analytics API Service
 */
class DocumentAnalyticsApiService {
  private readonly basePath = '/files';
  private readonly documentsPath = '/documents';

  /**
   * Get file statistics including type distribution and processing status
   */
  async getFileStats(): Promise<FileStatsResponse> {
    return apiClient.get<FileStatsResponse>(`${this.basePath}/stats`);
  }

  /**
   * Get paginated list of documents
   */
  async getDocuments(params: DocumentListParams = {}): Promise<DocumentListResponse> {
    const queryParams = new URLSearchParams();
    
    if (params.page) queryParams.append('page', params.page.toString());
    if (params.size) queryParams.append('size', params.size.toString());
    if (params.status) queryParams.append('status', params.status);
    if (params.document_type) queryParams.append('document_type', params.document_type);
    if (params.search) queryParams.append('search', params.search);
    if (params.sort_by) queryParams.append('sort_by', params.sort_by);
    if (params.sort_order) queryParams.append('sort_order', params.sort_order);
    if (params.tags?.length) {
      params.tags.forEach(tag => queryParams.append('tags', tag));
    }

    const queryString = queryParams.toString();
    const url = queryString 
      ? `${this.documentsPath}?${queryString}` 
      : this.documentsPath;

    return apiClient.get<DocumentListResponse>(url);
  }

  /**
   * Get single document details
   */
  async getDocument(documentId: string): Promise<DocumentResponse> {
    return apiClient.get<DocumentResponse>(`${this.documentsPath}/${documentId}`);
  }

  /**
   * Get document processing status
   */
  async getDocumentStatus(documentId: string): Promise<DocumentStatusResponse> {
    return apiClient.get<DocumentStatusResponse>(`${this.documentsPath}/${documentId}/status`);
  }

  /**
   * Get comprehensive document analytics
   * Aggregates data from multiple endpoints for dashboard display
   */
  async getDocumentAnalytics(): Promise<DocumentAnalytics> {
    try {
      // Fetch file stats
      const fileStats = await this.getFileStats();
      
      // Calculate totals
      const totalDocuments = fileStats.files_by_type.reduce((sum, item) => sum + item.count, 0);
      const totalStorageMb = fileStats.files_by_type.reduce((sum, item) => sum + item.total_size_mb, 0);
      
      // Transform file types
      const documentsByType: Record<string, number> = {};
      fileStats.files_by_type.forEach(item => {
        documentsByType[item.type] = item.count;
      });
      
      // Transform processing status
      const processingStatusCounts: Record<string, number> = {};
      fileStats.processing_stats.forEach(item => {
        processingStatusCounts[item.status] = item.count;
      });
      
      // Calculate average file size
      const averageFileSizeMb = totalDocuments > 0 ? totalStorageMb / totalDocuments : 0;
      
      // Get recent uploads (last 24 hours would require a separate endpoint, using completed as proxy)
      const recentUploadsCount = processingStatusCounts['pending'] || 0;

      return {
        total_documents: totalDocuments,
        total_storage_mb: totalStorageMb,
        documents_by_type: documentsByType,
        processing_status_counts: processingStatusCounts,
        average_file_size_mb: averageFileSizeMb,
        recent_uploads_count: recentUploadsCount,
      };
    } catch (error) {
      console.error('Failed to fetch document analytics:', error);
      throw error;
    }
  }

  /**
   * Get chart-ready file type distribution data
   */
  async getFileTypeDistribution(): Promise<Array<{ name: string; value: number }>> {
    const stats = await this.getFileStats();
    return stats.files_by_type.map(item => ({
      name: item.type.toUpperCase(),
      value: item.count,
    }));
  }

  /**
   * Get chart-ready processing status data
   */
  async getProcessingStatusDistribution(): Promise<Array<{ status: string; count: number }>> {
    const stats = await this.getFileStats();
    return stats.processing_stats.map(item => ({
      status: item.status,
      count: item.count,
    }));
  }
}

// Export singleton instance
export const documentAnalyticsApi = new DocumentAnalyticsApiService();
export default documentAnalyticsApi;
