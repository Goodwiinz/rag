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
} from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState, useMemo } from 'react';
import { Document as BaseDocument } from '@/types';

// Extended document type for UI needs if necessary
interface Document extends BaseDocument {
  // Add UI specific fields here if needed
  entities_count?: number;
}

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
    refreshDocuments,
  } = useDocuments({ autoFetch: true });

  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Update backend filters when local state changes
  useEffect(() => {
    const backendStatus = statusFilter === 'all' ? undefined : [statusFilter as any];
    updateFilters({ 
      search_term: searchQuery || undefined,
      status: backendStatus
    });
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
        return { color: 'var(--phosphor-green)', label: 'INDEXED', icon: CheckCircle };
      case 'processing':
        return { color: 'var(--cyan)', label: 'PROCESSING', icon: RefreshCw };
      case 'failed':
        return { color: '#ff4757', label: 'FAILED', icon: AlertTriangle };
      case 'queued':
      case 'pending':
        return { color: 'var(--amber-gold)', label: 'QUEUED', icon: Clock };
      default:
        return { color: '#6b7280', label: status.toUpperCase(), icon: Clock };
    }
  };

  const stats = useMemo(() => {
    return {
      total: pagination.total,
      indexed: rawDocuments.filter(d => d.processing_status === 'indexed').length, // This is only for current page, ideally should come from backend
      processing: rawDocuments.filter(d => d.processing_status === 'processing').length,
      failed: rawDocuments.filter(d => d.processing_status === 'failed').length,
    };
  }, [pagination.total, rawDocuments]);

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this document?')) {
      try {
        await deleteDocument(id);
      } catch (err) {
        console.error('Failed to delete document:', err);
        alert('Failed to delete document');
      }
    }
  };

  if (!mounted) return null;

  return (
    <div className="min-h-screen bg-[var(--terminal-bg)] flex flex-col">
      <div className="p-6 space-y-6 flex-1 overflow-y-auto terminal-scrollbar">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-6 shadow-xl"
        >
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-lg bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/20 flex items-center justify-center">
                <Folder className="w-6 h-6 text-[var(--phosphor-green)]" />
              </div>
              <div>
                <h1 className="text-xl font-mono font-bold text-[var(--terminal-text)] tracking-wider">
                  Document Repository
                </h1>
                <p className="text-xs font-mono text-[var(--terminal-text-dim)] mt-0.5 uppercase tracking-widest">
                  Knowledge Base Management
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => refreshDocuments()}
                className="p-2 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-surface)] text-[var(--terminal-text-dim)] hover:text-[var(--phosphor-green)] transition-all"
                title="Refresh Documents"
              >
                <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
              </button>
              <Link
                href="/documents/upload"
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--phosphor-green)] text-[var(--terminal-bg)] font-mono text-xs font-bold hover:shadow-[0_0_20px_var(--phosphor-green-glow)] transition-all active:scale-95"
              >
                <Upload className="w-3.5 h-3.5" />
                ADD DOCUMENTS
              </Link>
            </div>
          </div>
        </motion.div>

        {/* Stats Bar */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-4"
        >
          {[
            { label: 'TOTAL', value: stats.total, color: 'var(--terminal-text)' },
            { label: 'INDEXED', value: stats.indexed, color: 'var(--phosphor-green)' },
            { label: 'PROCESSING', value: stats.processing, color: 'var(--cyan)' },
            { label: 'FAILED', value: stats.failed, color: '#ff4757' },
          ].map((stat) => (
            <div
              key={stat.label}
              className="p-4 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-lg group relative overflow-hidden"
            >
              <div className="absolute top-0 left-0 w-1 h-full opacity-20 group-hover:opacity-100 transition-opacity" 
                   style={{ backgroundColor: stat.color }} />
              <div className="text-2xl font-mono font-bold text-[var(--terminal-text)]">
                {stat.value}
              </div>
              <div className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest mt-1">{stat.label}</div>
            </div>
          ))}
        </motion.div>

        {/* Search & Filter Bar */}
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative group">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--terminal-text-dim)] group-focus-within:text-[var(--phosphor-green)] transition-colors" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by title, filename, or tag..."
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-[var(--terminal-surface)] border border-[var(--terminal-border)] font-mono text-sm text-[var(--terminal-text)] outline-none focus:border-[var(--phosphor-green)]/30 transition-all shadow-lg"
            />
          </div>

          <div className="relative">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] text-xs font-mono text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] hover:border-[var(--terminal-border-glow)] transition-all shadow-lg"
            >
              <Filter className="w-4 h-4" />
              {statusFilter === 'all' ? 'STATUS: ALL' : statusFilter.toUpperCase()}
              <ChevronDown className={cn("w-4 h-4 transition-transform", showFilters && "rotate-180")} />
            </button>

            <AnimatePresence>
              {showFilters && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 10 }}
                  className="absolute right-0 mt-2 w-48 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-2xl z-20 overflow-hidden"
                >
                  {['all', 'indexed', 'processing', 'queued', 'failed'].map((status) => (
                    <button
                      key={status}
                      onClick={() => {
                        setStatusFilter(status);
                        setShowFilters(false);
                      }}
                      className={cn(
                        "w-full px-4 py-2.5 text-left font-mono text-xs transition-colors hover:bg-[var(--terminal-elevated)]",
                        statusFilter === status ? "text-[var(--phosphor-green)] bg-[var(--phosphor-green)]/5" : "text-[var(--terminal-text-dim)]"
                      )}
                    >
                      {status.toUpperCase()}
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="p-4 rounded-xl border border-red-500/20 bg-red-500/5 flex items-center gap-3 text-red-400 font-mono text-xs">
            <AlertTriangle className="w-4 h-4" />
            <span>{error}</span>
          </div>
        )}

        {/* Document List */}
        <div className="space-y-3">
          {loading && rawDocuments.length === 0 ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-24 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] animate-pulse" />
              ))}
            </div>
          ) : rawDocuments.length === 0 ? (
            <div className="text-center py-20 border-2 border-dashed border-[var(--terminal-border)] rounded-2xl bg-[var(--terminal-surface)]/30">
              <FileText className="w-12 h-12 mx-auto mb-4 text-[var(--terminal-text-muted)]" />
              <p className="text-[var(--terminal-text-dim)] font-mono text-sm">No records found matching current criteria</p>
            </div>
          ) : (
            rawDocuments.map((doc, index) => {
              const fileType = getFileTypeIcon(doc.file_type);
              const status = getStatusConfig(doc.processing_status);
              const StatusIcon = status.icon;

              return (
                <motion.div
                  key={doc.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.03 }}
                  className="group rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-4 shadow-lg hover:border-[var(--phosphor-green)]/20 transition-all"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-lg bg-[var(--terminal-bg)] border border-[var(--terminal-border)] flex items-center justify-center text-[var(--terminal-text-dim)] group-hover:text-[var(--phosphor-green)] transition-colors">
                      {fileType.icon}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3">
                        <h3 className="font-mono text-sm font-bold text-[var(--terminal-text)] truncate">
                          {doc.title || doc.filename}
                        </h3>
                        {doc.metadata?.entities_count && (
                          <div className="flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-[var(--amber-gold)]/10 border border-[var(--amber-gold)]/20 text-[9px] font-mono text-[var(--amber-gold)]">
                            <Sparkles className="w-2.5 h-2.5" />
                            {doc.metadata.entities_count} ENTITIES
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-1.5 text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-tighter">
                        <span>{doc.filename}</span>
                        <span className="opacity-30">|</span>
                        <span>{formatFileSize(doc.file_size)}</span>
                        <span className="opacity-30">|</span>
                        <span>{formatDate(doc.upload_timestamp)}</span>
                      </div>
                      {doc.tags && doc.tags.length > 0 && (
                        <div className="flex items-center gap-1.5 mt-2">
                          {doc.tags.map((tag) => (
                            <span
                              key={tag}
                              className="px-1.5 py-0.5 rounded bg-[var(--terminal-bg)] border border-[var(--terminal-border)] text-[9px] font-mono text-[var(--terminal-text-muted)]"
                            >
                              #{tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-4">
                      <div
                        className="flex items-center gap-1.5 px-2 py-1 rounded-lg border border-transparent font-mono text-[9px] font-bold"
                        style={{ color: status.color, backgroundColor: `${status.color}10` }}
                      >
                        <StatusIcon className={cn("w-3 h-3", doc.processing_status === 'processing' && "animate-spin")} />
                        {status.label}
                      </div>

                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity pr-2">
                        <Link 
                          href={`/documents/${doc.id}`}
                          className="p-2 rounded-lg hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)] hover:text-[var(--phosphor-green)] transition-all"
                        >
                          <Eye className="w-4 h-4" />
                        </Link>
                        <button className="p-2 rounded-lg hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] transition-all">
                          <Download className="w-4 h-4" />
                        </button>
                        <button 
                          onClick={() => handleDelete(doc.id)}
                          className="p-2 rounded-lg hover:bg-red-500/10 text-[var(--terminal-text-dim)] hover:text-red-400 transition-all"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                </motion.div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}