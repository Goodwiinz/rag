'use client';

import { useAuthStore } from '@/stores/authStore';
import { useDocuments } from '@/hooks/useDocuments';
import { Upload, RefreshCw, FolderOpen, AlertTriangle } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState, useMemo, useSyncExternalStore } from 'react';
import { Pagination } from '../../components/Pagination';
import { DocumentStats } from './components/DocumentStats';
import { DocumentFilters } from './components/DocumentFilters';
import { DocumentList } from './components/DocumentList';
import { Button } from '@/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { cn } from '@/lib/utils';
import toast from 'react-hot-toast';

/** Mount state can never change again for the life of this store. */
function _subscribeNever(): () => void {
  return () => {};
}

export default function DocumentsPage() {
  const { isAuthenticated } = useAuthStore();
  // Hydration guard: server always renders null (see getServerSnapshot),
  // client flips true on first paint. useSyncExternalStore instead of
  // useState+effect avoids the react-hooks/set-state-in-effect violation a
  // mount-flag effect would otherwise trip (see ChatInput.tsx for the same
  // pattern used elsewhere in this repo).
  const mounted = useSyncExternalStore(
    _subscribeNever,
    () => true,
    () => false
  );

  const {
    documents: rawDocuments,
    loading,
    error,
    pagination,
    filters,
    updateFilters,
    deleteDocument,
    deleteDocuments,
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
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState<string | null>(null);
  const [bulkDeleteDialogOpen, setBulkDeleteDialogOpen] = useState(false);

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
      visible_queued: rawDocuments.filter(
        (d) => d.processing_status === 'queued'
      ).length,
      visible_failed: rawDocuments.filter(
        (d) => d.processing_status === 'failed'
      ).length,
    };
  }, [pagination.total, rawDocuments]);

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e?.stopPropagation();
    setDocumentToDelete(id);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!documentToDelete) return;
    try {
      await deleteDocument(documentToDelete);
    } catch (err) {
      // The hook builds a per-file failure reason — surface it (R6-M14)
      // instead of closing the dialog as if the delete had succeeded.
      console.error('Failed to delete document:', err);
      toast.error(
        err instanceof Error ? err.message : 'Failed to delete document'
      );
    } finally {
      setDocumentToDelete(null);
      setDeleteDialogOpen(false);
    }
  };

  const handleBulkDelete = () => {
    setBulkDeleteDialogOpen(true);
  };

  const confirmBulkDelete = async () => {
    setIsBulkDeleting(true);
    try {
      // Single refetch after the whole batch, not one per id (R4-M22).
      await deleteDocuments(Array.from(selectedDocuments));
    } catch (err) {
      console.error('Failed to delete documents:', err);
      toast.error(
        err instanceof Error ? err.message : 'Failed to delete documents'
      );
    } finally {
      setIsBulkDeleting(false);
      setBulkDeleteDialogOpen(false);
    }
  };

  const handleRetry = async (id: string, e: React.MouseEvent) => {
    e?.stopPropagation();
    try {
      await retryDocument(id);
    } catch (err) {
      console.error('Failed to retry document:', err);
      toast.error(
        err instanceof Error ? err.message : 'Failed to retry document'
      );
    }
  };

  if (!mounted) return null;

  return (
    <div className="flex flex-col min-h-full bg-background">
      <div className="p-4 md:p-6 space-y-6 flex-1">
        {/* Header */}
        <div className="rounded-xl border border-border bg-card shadow-xs">
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

        {/* Status pills are page-scoped; Total is the filtered result count. */}
        <div className="space-y-2">
          <DocumentStats stats={stats} />
          <p className="text-xs text-muted-foreground">
            Status counts reflect the current page; total includes all matching
            documents.
          </p>
        </div>

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

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete document?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this document. This action cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={bulkDeleteDialogOpen}
        onOpenChange={setBulkDeleteDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {selectedDocuments.size} documents?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete {selectedDocuments.size} selected
              documents. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmBulkDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
