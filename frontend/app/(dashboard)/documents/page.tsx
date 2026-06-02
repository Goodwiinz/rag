'use client';

import { useAuthStore } from '@/stores/authStore';
import { useDocuments } from '@/hooks/useDocuments';
import { Upload, RefreshCw, Folder, AlertTriangle } from 'lucide-react';
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
    <div className="flex flex-col min-h-full bg-[var(--nous-bg-1)]">
      <div className="p-4 md:p-6 space-y-6 flex-1">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-lg bg-[var(--nous-sol)]/10 border border-[var(--nous-sol)]/20 flex items-center justify-center relative overflow-hidden group">
              <div className="absolute inset-0 bg-[var(--nous-sol)]/10 translate-y-full group-hover:translate-y-0 transition-transform duration-300" />
              <Folder className="w-6 h-6 text-[var(--nous-sol)] relative z-10" />
            </div>
            <div>
              <h1 className="text-2xl font-mono font-bold text-[var(--nous-fg-1)] tracking-wider flex items-center gap-2">
                DOCUMENT_REPOSITORY
                <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--nous-bg-3)] text-[var(--nous-fg-3)] border border-[var(--nous-border-1)]">
                  v2.0
                </span>
              </h1>
              <p className="text-xs font-mono text-[var(--nous-fg-3)] mt-0.5 uppercase tracking-widest">
                Knowledge Base Management System
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="icon"
              onClick={() => refreshDocuments()}
              className="border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] text-[var(--nous-fg-3)] hover:text-[var(--nous-sol)] hover:border-[var(--nous-sol)]/30"
              title="Refresh Documents"
            >
              <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
            </Button>
            <Link href="/documents/upload">
              <Button className="gap-2 bg-[var(--nous-sol)] text-[var(--nous-bg-1)] font-mono text-xs font-bold hover:shadow-[0_0_20px_var(--nous-sol-glow)] hover:bg-[var(--nous-sol)]/90">
                <Upload className="w-3.5 h-3.5" />
                UPLOAD_FILES
              </Button>
            </Link>
          </div>
        </div>

        {/* Stats Grid */}
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

        {/* Error Banner */}
        {error && (
          <div className="flex items-center gap-3 px-4 py-3 rounded-lg border border-red-500/30 bg-red-500/5">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <p className="text-red-400 font-mono text-sm">{error}</p>
          </div>
        )}

        {/* Document List */}
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
          <div className="mt-6 border-t border-[var(--nous-border-1)]/50 pt-4">
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
