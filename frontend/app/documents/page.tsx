/**
 * Documents List Page
 * Terminal Observatory themed document management interface
 */

'use client';

import { useAuthStore } from '@/stores/authStore';
import { cn } from '@/lib/utils';
import { useDocuments } from '@/hooks/useDocuments';
import { AnimatePresence, motion } from 'framer-motion';
import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  Clock,
  Download,
  Eye,
  FileText,
  Filter,
  Folder,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  Upload,
  X,
  RotateCcw,
  CheckSquare,
  Square,
  MoreVertical
} from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState, useMemo } from 'react';
import { Pagination } from '@/app/components/Pagination';

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
    updatePageSize
  } = useDocuments({ autoFetch: true, initialPageSize: 10 });

  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [showFilters, setShowFilters] = useState(false);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Update backend filters when local state changes
  useEffect(() => {
    const backendStatus = statusFilter === 'all' ? undefined : [statusFilter as any];
    const timeoutId = setTimeout(() => {
      updateFilters({ 
        search_term: searchQuery || undefined,
        status: backendStatus
      });
    }, 300); // Debounce search
    return () => clearTimeout(timeoutId);
  }, [searchQuery, statusFilter, updateFilters]);

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getFileTypeIcon = (type: string) => {
    if (!type) return { icon: <FileText className="w-4 h-4" />, color: '#6b7280' };
    const t = type.toLowerCase();
    if (t.includes('pdf')) return { icon: <FileText className="w-4 h-4" />, color: '#ff4757' };
    if (t.includes('document') || t.includes('docx')) return { icon: <FileText className="w-4 h-4" />, color: '#3b82f6' };
    if (t.includes('text')) return { icon: <FileText className="w-4 h-4" />, color: '#6b7280' };
    return { icon: <FileText className="w-4 h-4" />, color: '#6b7280' };
  };

  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'indexed':
      case 'completed':
        return { color: 'var(--phosphor-green)', label: 'INDEXED', icon: CheckCircle, canRetry: false };
      case 'processing':
        return { color: 'var(--cyan)', label: 'PROCESSING', icon: RefreshCw, canRetry: false };
      case 'failed':
        return { color: '#ff4757', label: 'FAILED', icon: AlertTriangle, canRetry: true };
      case 'queued':
      case 'pending':
        return { color: 'var(--amber-gold)', label: 'QUEUED', icon: Clock, canRetry: false };
      default:
        return { color: '#6b7280', label: status.toUpperCase(), icon: Clock, canRetry: false };
    }
  };

  const stats = useMemo(() => {
    return {
      total: pagination.total,
      visible_indexed: rawDocuments.filter(d => d.processing_status === 'indexed').length,
      visible_processing: rawDocuments.filter(d => d.processing_status === 'processing').length,
      visible_failed: rawDocuments.filter(d => d.processing_status === 'failed').length,
    };
  }, [pagination.total, rawDocuments]);

  const handleDelete = async (id: string, e?: React.MouseEvent) => {
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
    if (confirm(`Are you sure you want to delete ${selectedDocuments.size} documents?`)) {
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

  const handleRetry = async (id: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    try {
      await retryDocument(id);
    } catch (err) {
      console.error('Failed to retry document:', err);
    }
  };

  if (!mounted) return null;

  return (
    <div className="min-h-screen bg-[var(--terminal-bg)] flex flex-col">
      <div className="p-6 space-y-6 flex-1 overflow-y-auto terminal-scrollbar pb-20">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-lg bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/20 flex items-center justify-center relative overflow-hidden group">
              <div className="absolute inset-0 bg-[var(--phosphor-green)]/10 translate-y-full group-hover:translate-y-0 transition-transform duration-300" />
              <Folder className="w-6 h-6 text-[var(--phosphor-green)] relative z-10" />
            </div>
            <div>
              <h1 className="text-xl font-mono font-bold text-[var(--terminal-text)] tracking-wider flex items-center gap-2">
                DOCUMENT_REPOSITORY
                <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)] border border-[var(--terminal-border)]">
                  v2.0
                </span>
              </h1>
              <p className="text-xs font-mono text-[var(--terminal-text-dim)] mt-0.5 uppercase tracking-widest">
                Knowledge Base Management System
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => refreshDocuments()}
              className="p-2.5 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-surface)] text-[var(--terminal-text-dim)] hover:text-[var(--phosphor-green)] hover:border-[var(--phosphor-green)]/30 transition-all"
              title="Refresh Documents"
            >
              <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
            </button>
            <Link
              href="/documents/upload"
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[var(--phosphor-green)] text-[var(--terminal-bg)] font-mono text-xs font-bold hover:shadow-[0_0_20px_var(--phosphor-green-glow)] transition-all active:scale-95 group"
            >
              <Upload className="w-3.5 h-3.5 group-hover:-translate-y-0.5 transition-transform" />
              UPLOAD_FILES
            </Link>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'TOTAL_DOCS', value: stats.total, color: 'var(--terminal-text)', icon: Folder },
            { label: 'INDEXED_ON_PAGE', value: stats.visible_indexed, color: 'var(--phosphor-green)', icon: CheckCircle },
            { label: 'PROCESSING', value: stats.visible_processing, color: 'var(--cyan)', icon: RefreshCw },
            { label: 'FAILED', value: stats.visible_failed, color: '#ff4757', icon: AlertTriangle },
          ].map((stat) => (
            <div
              key={stat.label}
              className="p-4 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)]/50 backdrop-blur-sm relative overflow-hidden group hover:border-[var(--terminal-border-glow)] transition-colors"
            >
              <div className="absolute top-0 left-0 w-0.5 h-full opacity-50 group-hover:opacity-100 transition-all duration-500" 
                   style={{ backgroundColor: stat.color }} />
              <div className="flex justify-between items-start mb-2">
                <stat.icon className="w-4 h-4 opacity-50" style={{ color: stat.color }} />
                <div className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest">{stat.label}</div>
              </div>
              <div className="text-2xl font-mono font-bold text-[var(--terminal-text)]">
                {stat.value}
              </div>
            </div>
          ))}
        </div>

        {/* Bulk Actions Bar */}
        <AnimatePresence>
          {selectedDocuments.size > 0 && (
            <motion.div
              initial={{ opacity: 0, y: -20, height: 0 }}
              animate={{ opacity: 1, y: 0, height: 'auto' }}
              exit={{ opacity: 0, y: -20, height: 0 }}
              className="rounded-xl border border-[var(--phosphor-green)]/30 bg-[var(--phosphor-green)]/5 p-3 flex items-center justify-between overflow-hidden"
            >
              <div className="flex items-center gap-3 px-2">
                <CheckSquare className="w-4 h-4 text-[var(--phosphor-green)]" />
                <span className="font-mono text-sm text-[var(--phosphor-green)] font-bold">
                  {selectedDocuments.size} Selected
                </span>
                <div className="h-4 w-[1px] bg-[var(--phosphor-green)]/20 mx-2" />
                <button 
                  onClick={clearSelection}
                  className="text-xs font-mono text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] underline decoration-dotted"
                >
                  Clear Selection
                </button>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleBulkDelete}
                  disabled={isBulkDeleting}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-all font-mono text-xs font-bold disabled:opacity-50"
                >
                  {isBulkDeleting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                  DELETE_SELECTED
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Search & Filter */}
        <div className="flex flex-col md:flex-row gap-4 bg-[var(--terminal-surface)] p-1 rounded-xl border border-[var(--terminal-border)]">
          <div className="flex-1 relative group">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--terminal-text-dim)] group-focus-within:text-[var(--phosphor-green)] transition-colors" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search documents by name, content, or id..."
              className="w-full pl-10 pr-4 py-2 rounded-lg bg-transparent font-mono text-sm text-[var(--terminal-text)] outline-none placeholder:text-[var(--terminal-text-muted)]"
            />
          </div>

          <div className="w-[1px] bg-[var(--terminal-border)] my-1 hidden md:block" />

          <div className="relative">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="w-full md:w-auto flex items-center justify-between gap-3 px-4 py-2 rounded-lg text-xs font-mono text-[var(--terminal-text-dim)] hover:bg-[var(--terminal-elevated)] transition-all"
            >
              <div className="flex items-center gap-2">
                <Filter className="w-3.5 h-3.5" />
                <span>{statusFilter === 'all' ? 'ALL STATUS' : statusFilter.toUpperCase()}</span>
              </div>
              <ChevronDown className={cn("w-3.5 h-3.5 transition-transform", showFilters && "rotate-180")} />
            </button>

            <AnimatePresence>
              {showFilters && (
                <motion.div
                  initial={{ opacity: 0, y: 10, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 10, scale: 0.95 }}
                  className="absolute right-0 mt-2 w-48 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-2xl z-20 overflow-hidden"
                >
                  <div className="p-1">
                    {['all', 'indexed', 'processing', 'queued', 'failed'].map((status) => (
                      <button
                        key={status}
                        onClick={() => {
                          setStatusFilter(status);
                          setShowFilters(false);
                        }}
                        className={cn(
                          "w-full px-4 py-2 text-left font-mono text-xs rounded-lg transition-colors flex items-center justify-between group",
                          statusFilter === status 
                            ? "bg-[var(--phosphor-green)]/10 text-[var(--phosphor-green)]" 
                            : "text-[var(--terminal-text-dim)] hover:bg-[var(--terminal-elevated)] hover:text-[var(--terminal-text)]"
                        )}
                      >
                        {status.toUpperCase()}
                        {statusFilter === status && <CheckCircle className="w-3 h-3" />}
                      </button>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Document List */}
        <div className="space-y-3">
          {/* List Header */}
          <div className="px-4 py-2 flex items-center gap-4 text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest border-b border-[var(--terminal-border)]/50">
            <div className="w-5">
              <button onClick={selectAllDocuments} className="hover:text-[var(--terminal-text)]">
                {selectedDocuments.size > 0 && selectedDocuments.size === rawDocuments.length ? (
                  <CheckSquare className="w-4 h-4 text-[var(--phosphor-green)]" />
                ) : (
                  <Square className="w-4 h-4" />
                )}
              </button>
            </div>
            <div className="w-10 text-center">Type</div>
            <div className="flex-1">Name / Info</div>
            <div className="w-32 hidden md:block">Date</div>
            <div className="w-28">Status</div>
            <div className="w-24 text-right">Actions</div>
          </div>

          {loading && rawDocuments.length === 0 ? (
            <div className="space-y-3">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-20 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] animate-pulse" />
              ))}
            </div>
          ) : rawDocuments.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 border border-dashed border-[var(--terminal-border)] rounded-2xl bg-[var(--terminal-surface)]/30 group">
              <div className="w-16 h-16 rounded-2xl bg-[var(--terminal-elevated)] flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300">
                <Search className="w-8 h-8 text-[var(--terminal-text-muted)]" />
              </div>
              <h3 className="text-[var(--terminal-text)] font-mono font-bold mb-2">NO DOCUMENTS FOUND</h3>
              <p className="text-[var(--terminal-text-dim)] font-mono text-xs max-w-sm text-center mb-6">
                No documents match your current filters. Try adjusting your search criteria or upload new files.
              </p>
              <Link 
                href="/documents/upload"
                className="px-4 py-2 rounded-lg bg-[var(--terminal-elevated)] border border-[var(--terminal-border)] text-[var(--terminal-text)] font-mono text-xs hover:border-[var(--phosphor-green)] hover:text-[var(--phosphor-green)] transition-all"
              >
                UPLOAD NEW FILE
              </Link>
            </div>
          ) : (
            rawDocuments.map((doc, index) => {
              const fileType = getFileTypeIcon(doc.file_type);
              const status = getStatusConfig(doc.processing_status);
              const StatusIcon = status.icon;
              const isSelected = selectedDocuments.has(doc.id);

              return (
                <motion.div
                  key={doc.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.03 }}
                  onClick={() => selectDocument(doc.id)}
                  className={cn(
                    "group relative rounded-xl border bg-[var(--terminal-surface)] p-3 transition-all cursor-pointer",
                    isSelected 
                      ? "border-[var(--phosphor-green)] bg-[var(--phosphor-green)]/5" 
                      : "border-[var(--terminal-border)] hover:border-[var(--terminal-border-glow)]"
                  )}
                >
                  <div className="flex items-center gap-4">
                    {/* Checkbox */}
                    <div className="w-5 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                      <button 
                        onClick={() => selectDocument(doc.id)}
                        className={cn("transition-colors", isSelected ? "text-[var(--phosphor-green)]" : "text-[var(--terminal-text-muted)] hover:text-[var(--terminal-text)]")}
                      >
                        {isSelected ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4" />}
                      </button>
                    </div>

                    {/* Icon */}
                    <div className="w-10 h-10 rounded-lg bg-[var(--terminal-bg)] border border-[var(--terminal-border)] flex items-center justify-center flex-shrink-0 text-[var(--terminal-text-dim)] group-hover:text-[var(--phosphor-green)] transition-colors">
                      {fileType.icon}
                    </div>

                    {/* Main Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="font-mono text-sm font-bold text-[var(--terminal-text)] truncate">
                          {doc.title || doc.filename}
                        </h3>
                        {doc.metadata?.entities_count && (
                          <span className="hidden sm:flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-[var(--amber-gold)]/10 border border-[var(--amber-gold)]/20 text-[9px] font-mono text-[var(--amber-gold)]">
                            <Sparkles className="w-2.5 h-2.5" />
                            {doc.metadata.entities_count}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-1 text-[10px] font-mono text-[var(--terminal-text-dim)]">
                        <span className="uppercase tracking-tighter">{doc.file_type || 'Unknown'}</span>
                        <span className="w-1 h-1 rounded-full bg-[var(--terminal-border)]" />
                        <span>{formatFileSize(doc.file_size)}</span>
                      </div>
                    </div>

                    {/* Date (Desktop) */}
                    <div className="hidden md:block w-32 text-[10px] font-mono text-[var(--terminal-text-dim)]">
                      {formatDate(doc.upload_timestamp)}
                    </div>

                    {/* Status */}
                    <div className="w-28 flex-shrink-0">
                      <div
                        className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md border border-transparent font-mono text-[9px] font-bold"
                        style={{ color: status.color, backgroundColor: `${status.color}10` }}
                      >
                        <StatusIcon className={cn("w-3 h-3", doc.processing_status === 'processing' && "animate-spin")} />
                        {status.label}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="w-24 flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                       {status.canRetry && (
                          <button
                            onClick={(e) => handleRetry(doc.id, e)}
                            className="p-1.5 rounded-md hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)] hover:text-[var(--cyan)] transition-colors"
                            title="Retry Processing"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <Link 
                          href={`/documents/${doc.id}`}
                          className="p-1.5 rounded-md hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)] hover:text-[var(--phosphor-green)] transition-colors"
                          title="View Details"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </Link>
                        <button 
                          onClick={(e) => handleDelete(doc.id, e)}
                          className="p-1.5 rounded-md hover:bg-red-500/10 text-[var(--terminal-text-dim)] hover:text-red-400 transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                    </div>
                  </div>
                </motion.div>
              );
            })
          )}
        </div>

        {/* Pagination */}
        {!loading && pagination.total > 0 && (
          <div className="mt-6 border-t border-[var(--terminal-border)]/50 pt-4">
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
