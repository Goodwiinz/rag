import { useState, useEffect, useCallback } from 'react';
import { Document, DocumentListResponse, DocumentFilters } from '@/types';
import { RAGAPIClient } from '@/services/api';

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
  const {
    initialPageSize = 20,
    autoFetch = true,
  } = options;

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

  const apiClient = new RAGAPIClient();

  const fetchDocuments = useCallback(async (
    page: number = state.pagination.page,
    pageSize: number = state.pagination.pageSize,
    filters: DocumentFilters = state.filters
  ) => {
    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const params: Record<string, any> = {
        page,
        page_size: pageSize,
      };

      // Add filters to params
      if (filters.file_types && filters.file_types.length > 0) {
        params.file_type = filters.file_types.join(',');
      }
      if (filters.status && filters.status.length > 0) {
        params.status = filters.status.join(',');
      }
      if (filters.search_term) {
        params.search = filters.search_term;
      }
      if (filters.date_range) {
        params.date_from = filters.date_range.start;
        params.date_to = filters.date_range.end;
      }

      const response = await apiClient.getDocuments(params);

      setState(prev => ({
        ...prev,
        documents: response.documents,
        pagination: {
          page: response.pagination.page,
          pageSize: response.pagination.page_size,
          total: response.pagination.total,
          totalPages: response.pagination.total_pages || Math.ceil(response.pagination.total / response.pagination.page_size),
          hasNext: response.pagination.has_next,
          hasPrev: response.pagination.has_prev,
        },
        loading: false,
        error: null,
      }));
    } catch (error) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: error instanceof Error ? error.message : 'Failed to fetch documents',
      }));
    }
  }, [state.pagination.page, state.pagination.pageSize, state.filters, apiClient]);

  const updateFilters = useCallback((newFilters: Partial<DocumentFilters>) => {
    setState(prev => ({
      ...prev,
      filters: { ...prev.filters, ...newFilters },
      pagination: { ...prev.pagination, page: 1 }, // Reset to first page when filters change
    }));
  }, []);

  const updatePage = useCallback((page: number) => {
    setState(prev => ({
      ...prev,
      pagination: { ...prev.pagination, page },
    }));
  }, []);

  const updatePageSize = useCallback((pageSize: number) => {
    setState(prev => ({
      ...prev,
      pagination: { ...prev.pagination, pageSize, page: 1 }, // Reset to first page when page size changes
    }));
  }, []);

  const selectDocument = useCallback((documentId: string) => {
    setState(prev => {
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
    setState(prev => ({
      ...prev,
      selectedDocuments: new Set(prev.documents.map(doc => doc.id)),
    }));
  }, []);

  const clearSelection = useCallback(() => {
    setState(prev => ({
      ...prev,
      selectedDocuments: new Set(),
    }));
  }, []);

  const deleteDocument = useCallback(async (documentId: string) => {
    try {
      await apiClient.deleteDocument(documentId);

      // Refresh documents list
      await fetchDocuments();

      // Remove from selection if selected
      setState(prev => {
        const newSelected = new Set(prev.selectedDocuments);
        newSelected.delete(documentId);
        return { ...prev, selectedDocuments: newSelected };
      });
    } catch (error) {
      throw new Error(error instanceof Error ? error.message : 'Failed to delete document');
    }
  }, [apiClient, fetchDocuments]);

  const deleteSelectedDocuments = useCallback(async () => {
    const promises = Array.from(state.selectedDocuments).map(id =>
      deleteDocument(id)
    );

    try {
      await Promise.all(promises);
      clearSelection();
    } catch (error) {
      throw new Error('Failed to delete some documents');
    }
  }, [state.selectedDocuments, deleteDocument, clearSelection]);

  const refreshDocuments = useCallback(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const retryDocument = useCallback(async (documentId: string) => {
    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const result = await apiClient.retryDocumentProcessing(documentId);

      // Refresh documents list to get updated status
      await fetchDocuments();

      return result;
    } catch (error) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: error instanceof Error ? error.message : 'Failed to retry document processing',
      }));
      throw new Error(error instanceof Error ? error.message : 'Failed to retry document processing');
    }
  }, [apiClient, fetchDocuments]);

  // Auto-fetch on mount and when dependencies change
  useEffect(() => {
    if (autoFetch) {
      fetchDocuments();
    }
  }, [autoFetch, fetchDocuments]);

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