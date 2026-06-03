'use client';

import { useAuthStore } from '@/stores/authStore';
import { useDocuments } from '@/hooks/useDocuments';
import { Upload, RefreshCw, FolderOpen, AlertTriangle } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState, useMemo } from 'react';
import { Pagination } from '../../components/Pagination';
import { DocumentStats } from './components/DocumentStats';
import { DocumentFilters } from './components/DocumentFilters';
import { DocumentList } from './components/DocumentList';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export default function DocumentsPage() {
  const { isAuthenticated } = useAuthStore();
  const [mounted, setMounted] = useState(false);

  const {
    documents: rawDocuments,
    loading,
    error,
    pagination,
    filters,
    updateFilters,
    deleteDocument,
    deleteSelectedDocuments,
    refreshDocuments,
    selectDocument,
    selectAllDocuments,
    clearSelection,
    selectedDocuments,
    retryDocument,
    updatePage,
    updatePageSize,
  } = useDocuments({ autoFetch: true, initialPageSize: 10 });

  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Update backend filters when local state changes
  useEffect(() => {
    const backendStatus =
      statusFilter === 'all' ? undefined : [statusFilter as any];
    const timeoutId = setTimeout(() => {
      updateFilters({
        search_term: searchQuery || undefined,
        status: backendStatus,
      });
    }, 300); // Debounce search
    return () => clearTimeout(timeoutId);
  }, [searchQuery, statusFilter, updateFilters]);

  const stats = useMemo(() => {
    return {
      total: pagination.total,
      visible_indexed: rawDocuments.filter(
        (d) => d.processing_status === 'indexed'
      ).length,
      visible_processing: rawDocuments.filter(
        (d) => d.processing_status === 'processing'
      ).length,
      visible_failed: rawDocuments.filter(
        (d) => d.processing_status === 'failed'
      ).length,
    };
  }, [pagination.total, rawDocuments]);

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e?.stopPropagation();
    if (confirm('Are you sure you want to delete this document?')) {
      try {
        await deleteDocument(id);
      } catch (err) {
        console.error('Failed to delete document:', err);
        alert('Failed to delete document');
      }
    }
  };

  const handleBulkDelete = async () => {
    if (
      confirm(
        `Are you sure you want to delete ${selectedDocuments.size} documents?`
      )
    ) {
      setIsBulkDeleting(true);
      try {
        await deleteSelectedDocuments();
      } catch (err) {
        console.error('Failed to delete documents:', err);
        alert('Failed to delete some documents');
      } finally {
        setIsBulkDeleting(false);
      }
    }
  };

  const handleRetry = async (id: string, e: React.MouseEvent) => {
    e?.stopPropagation();
    try {
      await retryDocument(id);
    } catch (err) {
      console.error('Failed to retry document:', err);
    }
  };

  if (!mounted) return null;

  return (
    <div className="flex flex-col min-h-full bg-background">
      <div className="p-4 md:p-6 space-y-6 flex-1">
        {/* Header */}
        <div className="rounded-xl border border-border bg-card shadow-sm">
          <div className="p-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                  <FolderOpen
                    aria-hidden="true"
                    className="w-6 h-6 text-primary"
                  />
                </div>
                <div>
                  <h1 className="text-xl font-semibold text-foreground">
                    Documents
                  </h1>
                  <p className="text-sm text-muted-foreground mt-0.5">
                    Your knowledge base library
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => refreshDocuments()}
                  disabled={loading}
                  aria-label="Refresh documents"
                >
                  <RefreshCw
                    aria-hidden="true"
                    className={cn('w-4 h-4', loading && 'animate-spin')}
                  />
                </Button>
                <Button asChild className="gap-2">
                  <Link href="/documents/upload">
                    <Upload aria-hidden="true" className="w-4 h-4" />
                    Upload files
                  </Link>
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Stats */}
        <DocumentStats stats={stats} />

        {/* Filters */}
        <DocumentFilters
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          statusFilter={statusFilter}
          onStatusChange={setStatusFilter}
          selectedCount={selectedDocuments.size}
          onClearSelection={clearSelection}
          onBulkDelete={handleBulkDelete}
          isBulkDeleting={isBulkDeleting}
        />

        {/* Error */}
        {error && (
          <div
            role="alert"
            className="flex items-center gap-3 px-4 py-3 rounded-xl border border-destructive/40 bg-destructive/5"
          >
            <AlertTriangle
              aria-hidden="true"
              className="w-4 h-4 text-destructive shrink-0"
            />
            <p className="text-sm text-foreground">{error}</p>
          </div>
        )}

        {/* Document list */}
        <DocumentList
          documents={rawDocuments.map((doc) => ({
            ...doc,
            file_type: doc.file_type || '',
            file_size: doc.file_size || 0,
            upload_timestamp: doc.upload_timestamp || '',
            processing_status: doc.processing_status,
          }))}
          loading={loading}
          selectedDocuments={selectedDocuments}
          onSelect={selectDocument}
          onSelectAll={selectAllDocuments}
          onDelete={handleDelete}
          onRetry={handleRetry}
        />

        {/* Pagination */}
        {!loading && pagination.total > 0 && (
          <div className="mt-6 border-t border-border pt-4">
            <Pagination
              currentPage={pagination.page}
              totalPages={pagination.totalPages}
              pageSize={pagination.pageSize}
              totalItems={pagination.total}
              onPageChange={updatePage}
              onPageSizeChange={updatePageSize}
            />
          </div>
        )}
      </div>
    </div>
  );
}
