import { APIResponse, API_CONFIG } from '@/types/api';
import {
  Document,
  DocumentFilters,
  DocumentListResponse,
  UploadProgress,
} from '@/types/document';
import { api } from '@/services/api-client';

export class DocumentService {
  private readonly basePath = '/documents';

  /**
   * Get documents with pagination and filtering
   */
  async getDocuments(
    page: number = 1,
    pageSize: number = 20,
    filters?: DocumentFilters
  ): Promise<APIResponse<DocumentListResponse>> {
    const params: Record<string, any> = {
      page,
      page_size: pageSize,
    };

    if (filters) {
      if (filters.file_types?.length) {
        params.file_types = filters.file_types.join(',');
      }
      if (filters.status?.length) {
        params.status = filters.status.join(',');
      }
      if (filters.date_range) {
        params.date_from = filters.date_range.start;
        params.date_to = filters.date_range.end;
      }
      if (filters.search_term) {
        params.search = filters.search_term;
      }
    }

    const queryString = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined)
        .map(([k, v]) => [k, String(v)])
    ).toString();
    return api.get(`${this.basePath}${queryString ? `?${queryString}` : ''}`);
  }

  /**
   * Get document by ID
   */
  async getDocument(id: string): Promise<APIResponse<Document>> {
    return api.get(`${this.basePath}/${id}`);
  }

  /**
   * Update document metadata
   */
  async updateDocument(
    id: string,
    updates: Partial<
      Pick<Document, 'title' | 'description' | 'tags' | 'custom_fields'>
    >
  ): Promise<APIResponse<Document>> {
    return api.patch(`${this.basePath}/${id}`, updates);
  }

  /**
   * Delete document
   */
  async deleteDocument(id: string): Promise<APIResponse<void>> {
    return api.delete(`${this.basePath}/${id}`);
  }

  /**
   * Get upload progress
   */
  async getUploadProgress(jobId: string): Promise<APIResponse<UploadProgress>> {
    return api.get(`${this.basePath}/upload-progress/${jobId}`);
  }

  /**
   * Download document
   */
  async downloadDocument(id: string, filename?: string): Promise<void> {
    return api.download(`${this.basePath}/${id}/download`, filename);
  }

  /**
   * Get document preview (text snippet)
   */
  async getDocumentPreview(
    id: string
  ): Promise<APIResponse<{ preview: string }>> {
    return api.get(`${this.basePath}/${id}/preview`);
  }

  /**
   * Get document thumbnail
   */
  getDocumentThumbnailUrl(id: string): string {
    return `${API_CONFIG.BASE_URL}${this.basePath}/${id}/thumbnail`;
  }

  /**
   * Get processing status
   */
  async getProcessingStatus(id: string): Promise<APIResponse<UploadProgress>> {
    return api.get(`${this.basePath}/${id}/processing-status`);
  }

  /**
   * Retry failed processing
   */
  async retryProcessing(id: string): Promise<APIResponse<Document>> {
    return api.post(`${this.basePath}/${id}/retry-processing`);
  }

  /**
   * Search within documents
   */
  async searchDocuments(
    query: string,
    documentIds?: string[],
    limit: number = 10
  ): Promise<APIResponse<Document[]>> {
    const params: Record<string, any> = {
      q: query,
      limit,
    };

    if (documentIds?.length) {
      params.document_ids = documentIds.join(',');
    }

    const qs = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined)
        .map(([k, v]) => [k, String(v)])
    ).toString();
    return api.get(`${this.basePath}/search${qs ? `?${qs}` : ''}`);
  }

  /**
   * Get document statistics
   */
  async getDocumentStats(): Promise<
    APIResponse<{
      total_documents: number;
      total_size: number;
      by_file_type: Record<string, number>;
      by_status: Record<string, number>;
      recent_uploads: Document[];
    }>
  > {
    return api.get(`${this.basePath}/stats`);
  }
}

// Create singleton instance
export const documentService = new DocumentService();
