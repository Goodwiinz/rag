import { apiClient } from './apiClient';
import { APIResponse } from '@/types/api';
import {
  Document,
  DocumentListResponse,
  DocumentFilters,
  UploadProgress,
  DocumentUpload,
} from '@/types/document';

export class DocumentService {
  private readonly basePath = '/documents';

  /**
   * Upload a single file
   */
  async uploadFile(
    file: File,
    onProgress?: (progress: number) => void
  ): Promise<APIResponse<Document>> {
    return apiClient.upload(`${this.basePath}/upload`, file, onProgress);
  }

  /**
   * Upload multiple files
   */
  async uploadFiles(
    files: File[],
    onProgress?: (fileIndex: number, fileProgress: number, totalProgress: number) => void
  ): Promise<APIResponse<Document[]>> {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      // Progress tracking
      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable && onProgress) {
          const fileProgress = (event.loaded / event.total) * 100;
          // For simplicity, treat first file progress as overall progress
          onProgress(0, fileProgress, fileProgress);
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText) as APIResponse<Document[]>;
            resolve(response);
          } catch (error) {
            reject(new Error('Invalid response format'));
          }
        } else {
          reject(new Error(`Upload failed with status ${xhr.status}`));
        }
      });

      xhr.addEventListener('error', () => {
        reject(new Error('Network error during upload'));
      });

      xhr.open('POST', `${apiClient.client.defaults.baseURL}${this.basePath}/batch-upload`);

      // Add auth headers
      const token = localStorage.getItem('auth_token');
      const organizationId = localStorage.getItem('organization_id');
      if (token && organizationId) {
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);
        xhr.setRequestHeader('X-Organization-ID', organizationId);
      }

      xhr.send(formData);
    });
  }

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

    return apiClient.get(`${this.basePath}`, { params });
  }

  /**
   * Get document by ID
   */
  async getDocument(id: string): Promise<APIResponse<Document>> {
    return apiClient.get(`${this.basePath}/${id}`);
  }

  /**
   * Update document metadata
   */
  async updateDocument(
    id: string,
    updates: Partial<Pick<Document, 'title' | 'description' | 'tags' | 'custom_fields'>>
  ): Promise<APIResponse<Document>> {
    return apiClient.patch(`${this.basePath}/${id}`, updates);
  }

  /**
   * Delete document
   */
  async deleteDocument(id: string): Promise<APIResponse<void>> {
    return apiClient.delete(`${this.basePath}/${id}`);
  }

  /**
   * Get upload progress
   */
  async getUploadProgress(jobId: string): Promise<APIResponse<UploadProgress>> {
    return apiClient.get(`${this.basePath}/upload-progress/${jobId}`);
  }

  /**
   * Download document
   */
  async downloadDocument(id: string, filename?: string): Promise<void> {
    return apiClient.download(`${this.basePath}/${id}/download`, filename);
  }

  /**
   * Get document preview (text snippet)
   */
  async getDocumentPreview(id: string): Promise<APIResponse<{ preview: string }>> {
    return apiClient.get(`${this.basePath}/${id}/preview`);
  }

  /**
   * Get document thumbnail
   */
  getDocumentThumbnailUrl(id: string): string {
    const baseURL = apiClient.client.defaults.baseURL;
    return `${baseURL}${this.basePath}/${id}/thumbnail`;
  }

  /**
   * Get processing status
   */
  async getProcessingStatus(id: string): Promise<APIResponse<UploadProgress>> {
    return apiClient.get(`${this.basePath}/${id}/processing-status`);
  }

  /**
   * Retry failed processing
   */
  async retryProcessing(id: string): Promise<APIResponse<Document>> {
    return apiClient.post(`${this.basePath}/${id}/retry-processing`);
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

    return apiClient.get(`${this.basePath}/search`, { params });
  }

  /**
   * Get document statistics
   */
  async getDocumentStats(): Promise<APIResponse<{
    total_documents: number;
    total_size: number;
    by_file_type: Record<string, number>;
    by_status: Record<string, number>;
    recent_uploads: Document[];
  }>> {
    return apiClient.get(`${this.basePath}/stats`);
  }
}

// Create singleton instance
export const documentService = new DocumentService();