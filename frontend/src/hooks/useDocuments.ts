import { useState, useEffect, useCallback, useRef } from 'react';
import { Document, DocumentFilters, APIErrorClass } from '@/types';
import { api } from '@/services/api-client';
import { useAuth } from '@/hooks/useAuth';

// Type for the backend document response (before transformation)
interface BackendDocument {
  id: string;
  uploaded_by_user_id?: string;
  user_id?: string;
  organization_id?: string;
  title?: string;
  filename?: string;
  document_type?: string;
  file_type?: string;
  file_size_bytes?: number;
  file_size?: number;
  processing_status?: string;
  processing_error?: string;
  created_at?: string;
  upload_timestamp?: string;
  processing_completed_at?: string;
  thumbnail_url?: string;
  page_count?: number;
  duration_seconds?: number;
  extracted_text_preview?: string;
  metadata?: Record<string, unknown>;
  document_metadata?: Record<string, unknown>;
  description?: string;
  tags?: string[];
  custom_fields?: Record<string, unknown>;
  custom_metadata?: Record<string, unknown>;
}

// Type for the API response from /documents/ endpoint
interface DocumentsApiResponse {
  documents: BackendDocument[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages?: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

// Valid processing status values
const VALID_PROCESSING_STATUSES = [
  'queued',
  'processing',
  'indexed',
  'failed',
] as const;
type ValidProcessingStatus = (typeof VALID_PROCESSING_STATUSES)[number];

// Valid file type values — matches backend DocumentType enum
const VALID_FILE_TYPES = [
  'pdf',
  'txt',
  'jpg',
  'png',
  'mp3',
  'mp4',
  'text',
  'image',
  'audio',
  'video',
  'spreadsheet',
  'presentation',
  'multimodal',
] as const;
type ValidFileType = (typeof VALID_FILE_TYPES)[number];

// Helper to validate processing status
function normalizeProcessingStatus(
  status: string | undefined
): ValidProcessingStatus {
  const normalized = status?.toLowerCase();
  if (
    normalized &&
    VALID_PROCESSING_STATUSES.includes(normalized as ValidProcessingStatus)
  ) {
    return normalized as ValidProcessingStatus;
  }
  return 'queued';
}

// Helper to validate file type
function normalizeFileType(fileType: string | undefined): ValidFileType {
  const normalized = fileType?.toLowerCase();
  if (normalized && VALID_FILE_TYPES.includes(normalized as ValidFileType)) {
    return normalized as ValidFileType;
  }
  return 'pdf'; // Default to PDF if truly unknown
}

// Transform backend document response to frontend Document type
const transformDocument = (backendDoc: BackendDocument): Document => {
  return {
    id: backendDoc.id,
    user_id: backendDoc.uploaded_by_user_id || backendDoc.user_id || '',
    organization_id: backendDoc.organization_id || '',
    title: backendDoc.title || backendDoc.filename || 'Untitled',
    filename: backendDoc.filename || 'unknown',
    file_type: normalizeFileType(
      backendDoc.document_type || backendDoc.file_type
    ),
    file_size: backendDoc.file_size_bytes || backendDoc.file_size || 0,
    processing_status: normalizeProcessingStatus(backendDoc.processing_status),
    processing_error: backendDoc.processing_error,
    upload_timestamp:
      backendDoc.created_at ||
      backendDoc.upload_timestamp ||
      new Date().toISOString(),
    processing_completed_at: backendDoc.processing_completed_at,
    thumbnail_url: backendDoc.thumbnail_url,
    page_count: backendDoc.page_count,
    duration_seconds: backendDoc.duration_seconds,
    extracted_text_preview: backendDoc.extracted_text_preview,
    metadata: (backendDoc.metadata ||
      backendDoc.document_metadata ||
      {}) as Record<string, unknown>,
    description: backendDoc.description,
    tags: backendDoc.tags,
    custom_fields: (backendDoc.custom_fields || backendDoc.custom_metadata) as
      | Record<string, unknown>
      | undefined,
  };
};

interface UseDocumentsState {
  documents: Document[];
  loading: boolean;
  error: string | null;
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
    hasNext: boolean;
    hasPrev: boolean;
  };
  filters: DocumentFilters;
  selectedDocuments: Set<string>;
}

interface UseDocumentsOptions {
  initialPageSize?: number;
  autoFetch?: boolean;
}

export const useDocuments = (options: UseDocumentsOptions = {}) => {
  const { initialPageSize = 20, autoFetch = true } = options;

  const {
    isAuthenticated,
    isLoading: authLoading,
    handleAuthError,
  } = useAuth();

  const [state, setState] = useState<UseDocumentsState>({
    documents: [],
    loading: false,
    error: null,
    pagination: {
      page: 1,
      pageSize: initialPageSize,
      total: 0,
      totalPages: 0,
      hasNext: false,
      hasPrev: false,
    },
    filters: {},
    selectedDocuments: new Set(),
  });

  // Track if component is mounted to prevent state updates after unmount
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const fetchDocuments = useCallback(
    async (page?: number, pageSize?: number, filters?: DocumentFilters) => {
      // Check if user is authenticated before making API call
      console.log('🔍 Authentication check in fetchDocuments:', {
        isAuthenticated,
        authLoading,
      });

      if (!isAuthenticated) {
        console.warn('🚫 Cannot fetch documents: User not authenticated');
        setState((prev) => ({
          ...prev,
          loading: false,
          error: null, // Don't show error for unauthenticated users
        }));
        return;
      }

      console.log('Fetching documents with params:', {
        page,
        pageSize,
        filters,
        isAuthenticated,
        authLoading,
      });

      let actualPage: number = page ?? 1;
      let actualPageSize: number = pageSize ?? 20;
      let actualFilters: DocumentFilters = filters ?? {};

      // Get current values and set loading state atomically
      setState((prev) => {
        actualPage = page ?? prev.pagination.page;
        actualPageSize = pageSize ?? prev.pagination.pageSize;
        actualFilters = filters ?? prev.filters;
        return { ...prev, loading: true, error: null };
      });

      try {
        const params: Record<string, string | number> = {
          page: actualPage,
          page_size: actualPageSize,
        };

        // Add filters to params with proper null checks
        // Backend expects document_type and processing_status
        if (actualFilters?.file_types && actualFilters.file_types.length > 0) {
          params.document_type = actualFilters.file_types.join(',');
        }
        if (actualFilters?.status && actualFilters.status.length > 0) {
          params.processing_status = actualFilters.status.join(',');
        }
        if (actualFilters?.search_term) {
          params.search = actualFilters.search_term;
        }
        if (actualFilters?.date_range) {
          params.date_from = actualFilters.date_range.start;
          params.date_to = actualFilters.date_range.end;
        }

        console.log('Making API call to getDocuments with params:', params);
        const queryString = new URLSearchParams(
          Object.entries(params).map(([k, v]) => [k, String(v)])
        ).toString();
        const response = (await api.get(`/documents/?${queryString}`)) as DocumentsApiResponse;
        console.log('API response received:', response);

        // Check if response has the expected structure
        if (!response) {
          console.error('Empty API response:', response);
          setState((prev) => ({
            ...prev,
            loading: false,
            error: 'No response from server',
          }));
          return;
        }

        if (!response.pagination) {
          console.error('Invalid API response structure:', response);
          setState((prev) => ({
            ...prev,
            loading: false,
            error: 'Invalid response format from server',
          }));
          return;
        }

        // Transform backend documents to frontend format
        const transformedDocuments = (response.documents || []).map(
          transformDocument
        );

        setState((prev) => ({
          ...prev,
          documents: transformedDocuments,
          pagination: {
            page: response.pagination.page,
            pageSize: response.pagination.page_size,
            total: response.pagination.total,
            totalPages:
              response.pagination.total_pages ||
              Math.ceil(
                response.pagination.total / response.pagination.page_size
              ),
            hasNext: response.pagination.has_next,
            hasPrev: response.pagination.has_prev,
          },
          loading: false,
          error: null,
        }));
      } catch (error) {
        console.error('Error fetching documents:', error);

        // Handle APIErrorClass instances (from API client)
        if (error instanceof APIErrorClass) {
          console.log('APIErrorClass caught:', error.error);

          // Check if it's an authentication error (401/403)
          if (
            error.error.status_code === 401 ||
            error.error.status_code === 403
          ) {
            console.log(
              'Authentication error detected in APIErrorClass, triggering logout'
            );
            handleAuthError();
            setState((prev) => ({
              ...prev,
              loading: false,
              error:
                error.error.message ||
                'Your session has expired. Please log in again.',
            }));
            return;
          }

          // Handle other API errors
          setState((prev) => ({
            ...prev,
            loading: false,
            error: error.error.message || 'Request failed',
          }));
          return;
        }

        // Handle other error types (network errors, etc.)
        const errorMessage =
          error instanceof Error ? error.message : 'Unknown error';

        // Check for various authentication error patterns in error messages
        const isAuthError =
          errorMessage.includes('Could not validate credentials') ||
          errorMessage.includes('Authentication failed') ||
          errorMessage.includes('Unauthorized') ||
          errorMessage.includes('Invalid token') ||
          errorMessage.includes('Session expired');

        if (isAuthError) {
          console.log(
            'Authentication error detected in error message, triggering logout'
          );
          handleAuthError();
          setState((prev) => ({
            ...prev,
            loading: false,
            error: 'Your session has expired. Please log in again.',
          }));
          return;
        }

        setState((prev) => ({
          ...prev,
          loading: false,
          error: errorMessage,
        }));
      }
    },
    [handleAuthError, isAuthenticated, authLoading]
  );

  const updateFilters = useCallback(
    (newFilters: Partial<DocumentFilters>) => {
      let mergedFilters: DocumentFilters = {};
      let pageSize = 20;
      setState((prev) => {
        mergedFilters = { ...prev.filters, ...newFilters };
        pageSize = prev.pagination.pageSize;
        return {
          ...prev,
          filters: mergedFilters,
          pagination: { ...prev.pagination, page: 1 },
        };
      });
      // Fetch outside setState to avoid side effects in updater
      fetchDocuments(1, pageSize, mergedFilters);
    },
    [fetchDocuments]
  );

  const updatePage = useCallback(
    (page: number) => {
      let pageSize = 20;
      let filters: DocumentFilters = {};
      setState((prev) => {
        pageSize = prev.pagination.pageSize;
        filters = prev.filters;
        return {
          ...prev,
          pagination: { ...prev.pagination, page },
        };
      });
      fetchDocuments(page, pageSize, filters);
    },
    [fetchDocuments]
  );

  const updatePageSize = useCallback(
    (pageSize: number) => {
      let filters: DocumentFilters = {};
      setState((prev) => {
        filters = prev.filters;
        return {
          ...prev,
          pagination: { ...prev.pagination, pageSize, page: 1 },
        };
      });
      fetchDocuments(1, pageSize, filters);
    },
    [fetchDocuments]
  );

  const selectDocument = useCallback((documentId: string) => {
    setState((prev) => {
      const newSelected = new Set(prev.selectedDocuments);
      if (newSelected.has(documentId)) {
        newSelected.delete(documentId);
      } else {
        newSelected.add(documentId);
      }
      return { ...prev, selectedDocuments: newSelected };
    });
  }, []);

  const selectAllDocuments = useCallback(() => {
    setState((prev) => ({
      ...prev,
      selectedDocuments: new Set(prev.documents.map((doc) => doc.id)),
    }));
  }, []);

  const clearSelection = useCallback(() => {
    setState((prev) => ({
      ...prev,
      selectedDocuments: new Set(),
    }));
  }, []);

  const deleteDocument = useCallback(
    async (documentId: string) => {
      if (!isAuthenticated) {
        throw new Error('Authentication required to delete documents');
      }

      try {
        await api.delete(`/documents/${documentId}`);

        // Refresh documents list
        await fetchDocuments();

        // Remove from selection if selected
        setState((prev) => {
          const newSelected = new Set(prev.selectedDocuments);
          newSelected.delete(documentId);
          return { ...prev, selectedDocuments: newSelected };
        });
      } catch (error) {
        // Handle APIErrorClass instances (from API client)
        if (error instanceof APIErrorClass) {
          // Check if it's an authentication error (401/403)
          if (
            error.error.status_code === 401 ||
            error.error.status_code === 403
          ) {
            console.log(
              'Authentication error detected in deleteDocument, triggering logout'
            );
            handleAuthError();
            throw new Error('Your session has expired. Please log in again.');
          }
          throw new Error(error.error.message || 'Request failed');
        }

        // Handle other error types (network errors, etc.)
        const errorMessage =
          error instanceof Error ? error.message : 'Unknown error';

        // Check for various authentication error patterns in error messages
        const isAuthError =
          errorMessage.includes('Could not validate credentials') ||
          errorMessage.includes('Authentication failed') ||
          errorMessage.includes('Unauthorized') ||
          errorMessage.includes('Invalid token') ||
          errorMessage.includes('Session expired');

        if (isAuthError) {
          console.log(
            'Authentication error detected in deleteDocument error message, triggering logout'
          );
          handleAuthError();
          throw new Error('Your session has expired. Please log in again.');
        }
        throw new Error(errorMessage);
      }
    },
    [fetchDocuments, isAuthenticated, handleAuthError]
  );

  const deleteSelectedDocuments = useCallback(async () => {
    const documentIds = Array.from(state.selectedDocuments);

    // Use Promise.allSettled to handle partial failures
    const results = await Promise.allSettled(
      documentIds.map((id) => deleteDocument(id))
    );

    // Count successes and failures
    const failures = results.filter((r) => r.status === 'rejected');
    const successes = results.filter((r) => r.status === 'fulfilled');

    // Clear selection for successfully deleted documents
    clearSelection();

    // If there were any failures, throw an error with details
    if (failures.length > 0) {
      const errorMessage = `Failed to delete ${failures.length} of ${documentIds.length} documents. ${successes.length} documents were deleted successfully.`;
      throw new Error(errorMessage);
    }
  }, [state.selectedDocuments, deleteDocument, clearSelection]);

  const refreshDocuments = useCallback(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const retryDocument = useCallback(
    async (documentId: string) => {
      if (!isAuthenticated) {
        throw new Error('Authentication required to retry document processing');
      }

      setState((prev) => ({ ...prev, loading: true, error: null }));

      try {
        const result = await api.post(
          `/documents/${documentId}/reprocess`
        );

        // Refresh documents list to get updated status
        await fetchDocuments();

        return result;
      } catch (error) {
        // Handle APIErrorClass instances (from API client)
        if (error instanceof APIErrorClass) {
          // Check if it's an authentication error (401/403)
          if (
            error.error.status_code === 401 ||
            error.error.status_code === 403
          ) {
            console.log(
              'Authentication error detected in retryDocument, triggering logout'
            );
            handleAuthError();
            setState((prev) => ({
              ...prev,
              loading: false,
              error:
                error.error.message ||
                'Your session has expired. Please log in again.',
            }));
            return;
          }

          // Handle other API errors
          setState((prev) => ({
            ...prev,
            loading: false,
            error: error.error.message || 'Request failed',
          }));
          throw new Error(error.error.message || 'Request failed');
        }

        // Handle other error types (network errors, etc.)
        const errorMessage =
          error instanceof Error ? error.message : 'Unknown error';

        // Check for various authentication error patterns in error messages
        const isAuthError =
          errorMessage.includes('Could not validate credentials') ||
          errorMessage.includes('Authentication failed') ||
          errorMessage.includes('Unauthorized') ||
          errorMessage.includes('Invalid token') ||
          errorMessage.includes('Session expired');

        if (isAuthError) {
          console.log(
            'Authentication error detected in retryDocument error message, triggering logout'
          );
          handleAuthError();
          setState((prev) => ({
            ...prev,
            loading: false,
            error: 'Your session has expired. Please log in again.',
          }));
          return;
        }

        setState((prev) => ({
          ...prev,
          loading: false,
          error: errorMessage,
        }));
        throw new Error(errorMessage);
      }
    },
    [fetchDocuments, isAuthenticated, handleAuthError]
  );

  // Auto-fetch on mount and when dependencies change
  useEffect(() => {
    console.log('Auto-fetch effect triggered:', {
      autoFetch,
      isAuthenticated,
      authLoading,
      shouldFetch: autoFetch && isAuthenticated && !authLoading,
    });

    if (autoFetch && isAuthenticated && !authLoading) {
      console.log('Auto-fetching documents...');
      fetchDocuments();
    }
  }, [autoFetch, fetchDocuments, isAuthenticated, authLoading]);

  return {
    // State
    documents: state.documents,
    loading: state.loading,
    error: state.error,
    pagination: state.pagination,
    filters: state.filters,
    selectedDocuments: state.selectedDocuments,
    selectedCount: state.selectedDocuments.size,
    hasSelection: state.selectedDocuments.size > 0,
    isAllSelected: state.selectedDocuments.size === state.documents.length,

    // Actions
    fetchDocuments,
    updateFilters,
    updatePage,
    updatePageSize,
    selectDocument,
    selectAllDocuments,
    clearSelection,
    deleteDocument,
    deleteSelectedDocuments,
    refreshDocuments,
    retryDocument,
  };
};

export default useDocuments;
