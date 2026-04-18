import { motion } from 'framer-motion';
import {
  FileText, CheckSquare, Square, Search, Sparkles, CheckCircle,
  RefreshCw, AlertTriangle, Clock, RotateCcw, Eye, Trash2
} from 'lucide-react';
import { cn } from '@/lib/utils';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';

export interface Document {
  id: string;
  title: string;
  filename: string;
  file_type: string;
  file_size: number;
  upload_timestamp: string;
  processing_status: string;
  metadata?: {
    entities_count?: number;
  };
}

interface DocumentListProps {
  documents: Document[];
  loading: boolean;
  selectedDocuments: Set<string>;
  onSelect: (id: string) => void;
  onSelectAll: () => void;
  onDelete: (id: string, e: React.MouseEvent) => void;
  onRetry: (id: string, e: React.MouseEvent) => void;
}

export function DocumentList({
  documents,
  loading,
  selectedDocuments,
  onSelect,
  onSelectAll,
  onDelete,
  onRetry
}: DocumentListProps) {
  const router = useRouter();

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

  return (
    <div className="space-y-2 overflow-x-auto pb-4">
      <div className="min-w-[600px]">
        {/* List Header */}
        <div className="px-4 py-2 grid grid-cols-[20px_40px_1fr_128px_112px_96px] items-center gap-4 text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest">
          <div className="w-5 flex justify-center">
            <button onClick={onSelectAll} className="hover:text-[var(--terminal-text)] transition-colors">
              {selectedDocuments.size > 0 && selectedDocuments.size === documents.length ? (
                <CheckSquare className="w-4 h-4 text-[var(--phosphor-green)]" />
              ) : (
                <Square className="w-4 h-4" />
              )}
            </button>
          </div>
          <div className="w-10 text-center">Type</div>
          <div className="">Name / Info</div>
          <div className="w-32 hidden md:block">Date</div>
          <div className="w-28">Status</div>
          <div className="w-24 text-right">Actions</div>
        </div>

        {loading && documents.length === 0 ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-20 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] animate-pulse" />
            ))}
          </div>
        ) : documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 border border-dashed border-[var(--terminal-border)] rounded-b-xl bg-[var(--terminal-surface)]/30 group">
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
          documents.map((doc, index) => {
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
                onClick={() => onSelect(doc.id)}
                className={cn(
                  "group relative rounded-xl border bg-[var(--terminal-surface)] px-4 py-3 transition-all cursor-pointer mb-2 grid grid-cols-[20px_40px_1fr_128px_112px_96px] items-center gap-4",
                  isSelected
                    ? "border-[var(--phosphor-green)] bg-[var(--phosphor-green)]/5"
                    : "border-[var(--terminal-border)] hover:border-[var(--terminal-border-glow)] hover:shadow-lg hover:shadow-[var(--terminal-border-glow)]/10"
                )}
              >
                {/* Checkbox */}
                <div className="w-5 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                  <button
                    onClick={() => onSelect(doc.id)}
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
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-mono text-sm font-bold text-[var(--terminal-text)] truncate group-hover:text-[var(--phosphor-green)] transition-colors">
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
                <div className="w-24 flex items-center justify-end gap-1 opacity-60 group-hover:opacity-100 transition-opacity" onClick={(e) => e.stopPropagation()}>
                   {status.canRetry && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={(e) => onRetry(doc.id, e)}
                        className="h-8 w-8 hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)] hover:text-[var(--cyan)]"
                        title="Retry Processing"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)] hover:text-[var(--phosphor-green)]"
                      title="View Details"
                      onClick={(e) => {
                        e.stopPropagation();
                        router.push(`/documents/${doc.id}`);
                      }}
                    >
                      <Eye className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={(e) => onDelete(doc.id, e)}
                      className="h-8 w-8 hover:bg-red-500/10 text-[var(--terminal-text-dim)] hover:text-red-400"
                      title="Delete"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                </div>
              </motion.div>
            );
        })
      )}
      </div>
    </div>
  );
}
