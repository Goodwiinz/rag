/**
 * Mock Document Service
 * Simulates document upload functionality for demonstration purposes
 */

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

class MockDocumentService {
  private websocketConnections: Map<string, any> = new Map();
  private storageKey = 'mock_documents_storage';

  // Get stored documents from localStorage
  private getStoredDocuments(): any[] {
    if (typeof window === 'undefined') return [];

    try {
      const stored = localStorage.getItem(this.storageKey);
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.error('Error reading stored documents:', error);
      return [];
    }
  }

  // Save documents to localStorage
  private saveStoredDocuments(documents: any[]): void {
    if (typeof window === 'undefined') return;

    try {
      localStorage.setItem(this.storageKey, JSON.stringify(documents));
    } catch (error) {
      console.error('Error saving documents:', error);
    }
  }

  // Add document to storage
  private addDocumentToStorage(document: any): void {
    const documents = this.getStoredDocuments();
    documents.push({
      ...document,
      id: document.document_id,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    });
    this.saveStoredDocuments(documents);
  }

  // Get documents with pagination and filtering
  getDocuments(params: {
    page?: number;
    page_size?: number;
    file_type?: string;
    status?: string;
    search?: string;
    date_from?: string;
    date_to?: string;
  }): { documents: any[]; pagination: any } {
    let documents = this.getStoredDocuments();

    // Apply filters
    if (params.file_type) {
      const types = params.file_type.split(',');
      documents = documents.filter(doc => types.some(type => doc.mime_type?.includes(type.trim())));
    }

    if (params.status) {
      const statuses = params.status.split(',');
      documents = documents.filter(doc => statuses.some(status => doc.processing_status?.includes(status.trim())));
    }

    if (params.search) {
      const searchLower = params.search.toLowerCase();
      documents = documents.filter(doc =>
        doc.title?.toLowerCase().includes(searchLower) ||
        doc.filename?.toLowerCase().includes(searchLower) ||
        doc.description?.toLowerCase().includes(searchLower)
      );
    }

    // Sort by created_at (newest first)
    documents.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    // Apply pagination
    const page = params.page || 1;
    const pageSize = params.page_size || 20;
    const startIndex = (page - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    const paginatedDocuments = documents.slice(startIndex, endIndex);

    return {
      documents: paginatedDocuments,
      pagination: {
        page,
        page_size: pageSize,
        total: documents.length,
        total_pages: Math.ceil(documents.length / pageSize),
        has_next: endIndex < documents.length,
        has_prev: page > 1
      }
    };
  }

  /**
   * Mock document upload with simulated progress
   */
  async uploadDocument(
    file: File,
    request: DocumentUploadRequest,
    onProgress?: (update: WebSocketProgressUpdate) => void
  ): Promise<{ response: DocumentUploadResponse; websocket: any }> {
    const uploadId = `upload_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const documentId = `doc_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const jobId = `job_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    const response: DocumentUploadResponse = {
      document_id: documentId,
      upload_id: uploadId,
      title: request.title || file.name,
      filename: file.name,
      document_type: this.getDocumentType(file),
      file_size_bytes: file.size,
      file_size_mb: Math.round(file.size / (1024 * 1024) * 100) / 100,
      mime_type: file.type,
      processing_status: 'pending',
      job_id: jobId,
      estimated_processing_time: this.estimateProcessingTime(file),
      quality_score: 0.85 + Math.random() * 0.15, // Random quality score between 85-100%
      security_scan_result: {
        scan_status: 'passed',
        virus_detected: false,
        suspicious_content: false,
        file_integrity: 'verified',
        scan_timestamp: new Date().toISOString(),
        threats: [],
        warnings: []
      },
      upload_progress: 0,
      message: 'Upload initiated successfully',
      created_at: new Date().toISOString()
    };

    // Store the document for retrieval
    this.addDocumentToStorage(response);

    // Create mock websocket
    const websocket = this.createMockWebSocket(uploadId, onProgress);

    return { response, websocket };
  }

  /**
   * Validate file before upload
   */
  validateFile(file: File): { isValid: boolean; errors: string[] } {
    const errors: string[] = [];

    // Supported file types
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

    if (!supportedTypes[file.type as keyof typeof supportedTypes]) {
      errors.push(`Unsupported file type: ${file.type}`);
    }

    // Check file size (50MB limit)
    const maxSize = 50 * 1024 * 1024;
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
   * Estimate processing time for a file
   */
  estimateProcessingTime(file: File): number {
    const baseTime = 30;
    const sizeTime = (file.size / (1024 * 1024)) * 1;
    const typeMultipliers = {
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
    const multiplier = typeMultipliers[file.type as keyof typeof typeMultipliers] || 1.0;
    return Math.ceil((baseTime + sizeTime) * multiplier);
  }

  /**
   * Cancel an upload
   */
  async cancelUpload(uploadId: string): Promise<{ message: string }> {
    const websocket = this.websocketConnections.get(uploadId);
    if (websocket) {
      websocket.close();
      this.websocketConnections.delete(uploadId);
    }
    return { message: `Upload ${uploadId} cancelled` };
  }

  /**
   * Close all websocket connections
   */
  closeAllConnections(): void {
    this.websocketConnections.forEach((websocket, uploadId) => {
      websocket.close();
    });
    this.websocketConnections.clear();
  }

  private getDocumentType(file: File): string {
    if (file.type.includes('pdf')) return 'PDF';
    if (file.type.includes('image')) return 'Image';
    if (file.type.includes('audio')) return 'Audio';
    if (file.type.includes('video')) return 'Video';
    if (file.type.includes('text') || file.type.includes('document')) return 'Document';
    return 'Other';
  }

  private createMockWebSocket(uploadId: string, onProgress?: (update: WebSocketProgressUpdate) => void): any {
    const mockWebSocket = {
      close: () => {},
      send: () => {},
      readyState: 1, // OPEN
      onmessage: null,
      onopen: null,
      onerror: null,
      onclose: null
    };

    this.websocketConnections.set(uploadId, mockWebSocket);

    // Simulate progress updates
    const steps = [
      { step: 'Validating file', progress: 10 },
      { step: 'Scanning for security threats', progress: 25 },
      { step: 'Extracting content', progress: 40 },
      { step: 'Analyzing document structure', progress: 55 },
      { step: 'Extracting entities', progress: 70 },
      { step: 'Building knowledge graph', progress: 85 },
      { step: 'Finalizing processing', progress: 95 },
      { step: 'Completed', progress: 100 }
    ];

    let currentStep = 0;
    const interval = setInterval(() => {
      if (currentStep >= steps.length) {
        clearInterval(interval);

        // Send completion event
        if (onProgress) {
          onProgress({
            type: 'upload_complete',
            upload_id: uploadId,
            progress_percentage: 100,
            current_step: 'Completed',
            total_steps: steps.length,
            completed_steps: steps.length,
            result: {
              document_id: `doc_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
              title: 'Document processed successfully',
              status: 'completed'
            },
            timestamp: new Date().toISOString()
          });
        }
        return;
      }

      const stepData = steps[currentStep];
      if (onProgress) {
        onProgress({
          type: 'progress_update',
          upload_id: uploadId,
          progress_percentage: stepData.progress,
          current_step: stepData.step,
          total_steps: steps.length,
          completed_steps: currentStep + 1,
          timestamp: new Date().toISOString()
        });
      }

      currentStep++;
    }, 1000 + Math.random() * 2000); // Random delay between 1-3 seconds

    return mockWebSocket;
  }
}

export const mockDocumentService = new MockDocumentService();
export const uploadDocument = mockDocumentService.uploadDocument.bind(mockDocumentService);
export const cancelUpload = mockDocumentService.cancelUpload.bind(mockDocumentService);