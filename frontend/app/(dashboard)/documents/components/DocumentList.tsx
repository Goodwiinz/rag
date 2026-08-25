import {
  FixedSizeList as List,
  type ListChildComponentProps,
} from 'react-window';
import type { CSSProperties, MouseEvent } from 'react';
import {
  FileText,
  CheckSquare,
  Square,
  Sparkles,
  CheckCircle2,
  Loader,
  AlertTriangle,
  Clock,
  RotateCcw,
  Eye,
  Trash2,
  FolderOpen,
  LucideIcon,
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
  onDelete: (id: string, e: MouseEvent) => void;
  onRetry: (id: string, e: MouseEvent) => void;
}

const ROW_HEIGHT = 80;

interface StatusConfig {
  className: string;
  label: string;
  icon: LucideIcon;
  canRetry: boolean;
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.min(
    Math.floor(Math.log(bytes) / Math.log(k)),
    sizes.length - 1
  );
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
};

const formatDate = (dateString: string): string => {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const getStatusConfig = (status: string): StatusConfig => {
  switch (status) {
    case 'indexed':
    case 'completed':
      return {
        className:
          'text-(--nous-terra) bg-(--nous-terra)/10 border-(--nous-terra)/20',
        label: 'Indexed',
        icon: CheckCircle2,
        canRetry: false,
      };
    case 'processing':
      return {
        className:
          'text-(--nous-helios) bg-(--nous-helios)/10 border-(--nous-helios)/20',
        label: 'Processing',
        icon: Loader,
        canRetry: false,
      };
    case 'failed':
      return {
        className:
          'text-(--nous-mars) bg-(--nous-mars)/10 border-(--nous-mars)/20',
        label: 'Failed',
        icon: AlertTriangle,
        canRetry: true,
      };
    case 'queued':
    case 'pending':
      return {
        className: 'text-primary bg-primary/10 border-primary/20',
        label: 'Queued',
        icon: Clock,
        canRetry: false,
      };
    default:
      return {
        className: 'text-muted-foreground bg-muted border-border',
        label: status.charAt(0).toUpperCase() + status.slice(1),
        icon: Clock,
        canRetry: false,
      };
  }
};

interface DocumentRowData {
  documents: Document[];
  selectedDocuments: Set<string>;
  onSelect: (id: string) => void;
  onDelete: (id: string, event: MouseEvent) => void;
  onRetry: (id: string, event: MouseEvent) => void;
}

function DocumentRow({
  index,
  style,
  data,
}: ListChildComponentProps<DocumentRowData>) {
  const router = useRouter();
  const doc = data.documents[index];
  const status = getStatusConfig(doc.processing_status);
  const StatusIcon = status.icon;
  const isSelected = data.selectedDocuments.has(doc.id);

  return (
    <div style={style as CSSProperties}>
      <div
        onClick={() => data.onSelect(doc.id)}
        className={cn(
          'group relative rounded-xl border bg-card px-4 py-3 transition-all duration-200 cursor-pointer mb-2 grid grid-cols-[20px_40px_1fr_128px_112px_96px] items-center gap-4 shadow-xs',
          isSelected
            ? 'border-primary bg-primary/5'
            : 'border-border hover:bg-muted/50 hover:shadow-md'
        )}
      >
        <div
          className="w-5 shrink-0"
          onClick={(event) => event.stopPropagation()}
        >
          <button
            type="button"
            onClick={() => data.onSelect(doc.id)}
            aria-label={isSelected ? 'Deselect document' : 'Select document'}
            className={cn(
              'transition-colors rounded focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
              isSelected
                ? 'text-primary'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            {isSelected ? (
              <CheckSquare aria-hidden="true" className="w-4 h-4" />
            ) : (
              <Square aria-hidden="true" className="w-4 h-4" />
            )}
          </button>
        </div>

        <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center shrink-0 text-muted-foreground group-hover:text-primary transition-colors">
          <FileText aria-hidden="true" className="w-4 h-4" />
        </div>

        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium text-foreground truncate">
              {doc.title || doc.filename}
            </h3>
            {doc.metadata?.entities_count ? (
              <span className="hidden sm:flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-primary/10 border border-primary/20 text-[10px] text-primary tabular-nums">
                <Sparkles aria-hidden="true" className="w-2.5 h-2.5" />
                {doc.metadata.entities_count}
              </span>
            ) : null}
          </div>
          <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
            <span className="uppercase">{doc.file_type || 'Unknown'}</span>
            <span
              aria-hidden="true"
              className="w-1 h-1 rounded-full bg-border"
            />
            <span>{formatFileSize(doc.file_size)}</span>
          </div>
        </div>

        <div className="hidden md:block w-32 text-xs text-muted-foreground">
          {formatDate(doc.upload_timestamp)}
        </div>

        <div className="w-28 shrink-0">
          <span
            className={cn(
              'inline-flex items-center gap-1.5 px-2 py-1 rounded-md border text-[11px] font-medium',
              status.className
            )}
          >
            <StatusIcon aria-hidden="true" className="w-3 h-3" />
            {status.label}
          </span>
        </div>

        <div
          className="w-24 flex items-center justify-end gap-1 opacity-60 group-hover:opacity-100 transition-opacity"
          onClick={(event) => event.stopPropagation()}
        >
          {status.canRetry && (
            <Button
              variant="ghost"
              size="icon"
              onClick={(event) => data.onRetry(doc.id, event)}
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              aria-label="Retry processing"
            >
              <RotateCcw aria-hidden="true" className="w-4 h-4" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            aria-label="View details"
            onClick={() => router.push(`/documents/${doc.id}`)}
          >
            <Eye aria-hidden="true" className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={(event) => data.onDelete(doc.id, event)}
            className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
            aria-label="Delete document"
          >
            <Trash2 aria-hidden="true" className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

export function DocumentList({
  documents,
  loading,
  selectedDocuments,
  onSelect,
  onSelectAll,
  onDelete,
  onRetry,
}: DocumentListProps) {
  const allSelected =
    selectedDocuments.size > 0 && selectedDocuments.size === documents.length;

  return (
    <div className="space-y-2 overflow-x-auto pb-4">
      <div className="min-w-[600px]">
        {/* List header */}
        <div className="px-4 py-2 grid grid-cols-[20px_40px_1fr_128px_112px_96px] items-center gap-4 text-xs text-muted-foreground">
          <div className="w-5 flex justify-center">
            <button
              type="button"
              onClick={onSelectAll}
              aria-label={
                allSelected ? 'Deselect all documents' : 'Select all documents'
              }
              className="text-muted-foreground hover:text-foreground transition-colors rounded focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              {allSelected ? (
                <CheckSquare
                  aria-hidden="true"
                  className="w-4 h-4 text-primary"
                />
              ) : (
                <Square aria-hidden="true" className="w-4 h-4" />
              )}
            </button>
          </div>
          <div className="w-10 text-center">Type</div>
          <div>Name</div>
          <div className="w-32 hidden md:block">Uploaded</div>
          <div className="w-28">Status</div>
          <div className="w-24 text-right">Actions</div>
        </div>

        {loading && documents.length === 0 ? (
          <div
            className="space-y-2"
            role="status"
            aria-label="Loading documents"
          >
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-16 rounded-xl border border-border bg-card animate-pulse"
              />
            ))}
          </div>
        ) : documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 border border-dashed border-border rounded-xl bg-card">
            <div className="w-14 h-14 rounded-xl bg-muted flex items-center justify-center mb-4">
              <FolderOpen
                aria-hidden="true"
                className="w-7 h-7 text-muted-foreground"
              />
            </div>
            <h3 className="text-base font-medium text-foreground mb-1.5">
              No documents yet
            </h3>
            <p className="text-sm text-muted-foreground max-w-sm text-center mb-6">
              Upload your first document to build your knowledge base. PDF,
              DOCX, TXT, images, audio, and video are supported.
            </p>
            <Button asChild className="gap-2">
              <Link href="/documents/upload">Upload a document</Link>
            </Button>
          </div>
        ) : (
          <List
            height={Math.min(documents.length * ROW_HEIGHT, 600)}
            itemCount={documents.length}
            itemData={{
              documents,
              selectedDocuments,
              onSelect,
              onDelete,
              onRetry,
            }}
            itemSize={ROW_HEIGHT}
            width="100%"
          >
            {DocumentRow}
          </List>
        )}
      </div>
    </div>
  );
}
