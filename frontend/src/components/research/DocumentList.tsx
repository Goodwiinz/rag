'use client';

import { useState, useMemo, useCallback } from 'react';
import {
  FileText,
  Search,
  Trash2,
  MoreHorizontal,
  ArrowUpDown,
  ExternalLink,
  X,
  File,
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { IconButton } from '@/components/ui/icon-button';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { ProjectDocument } from '@/services/projectService';

interface DocumentListProps {
  documents: ProjectDocument[];
  loading: boolean;
  onRemove: (documentId: string) => void;
}

type SortKey = 'title' | 'added_at';
type SortDir = 'asc' | 'desc';

const statusConfig: Record<
  string,
  { label: string; variant: 'success' | 'warning' | 'info' | 'secondary' }
> = {
  completed: { label: 'Indexed', variant: 'success' },
  indexed: { label: 'Indexed', variant: 'success' },
  processing: { label: 'Processing', variant: 'warning' },
  pending: { label: 'Queued', variant: 'info' },
  queued: { label: 'Queued', variant: 'info' },
  failed: { label: 'Failed', variant: 'secondary' },
};

function getFileIcon(filename?: string) {
  if (!filename) return <FileText className="h-5 w-5" />;
  const ext = filename.split('.').pop()?.toLowerCase();
  if (ext === 'pdf') return <File className="h-5 w-5 text-red-400" />;
  return <FileText className="h-5 w-5" />;
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export function DocumentList({
  documents,
  loading,
  onRemove,
}: DocumentListProps) {
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('added_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const filtered = useMemo(() => {
    let result = documents;
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (doc) =>
          (doc.document?.title || '').toLowerCase().includes(q) ||
          (doc.document?.filename || '').toLowerCase().includes(q)
      );
    }
    result = [...result].sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'title') {
        cmp = (a.document?.title || '').localeCompare(b.document?.title || '');
      } else {
        cmp =
          new Date(a.added_at || a.document?.created_at || 0).getTime() -
          new Date(b.added_at || b.document?.created_at || 0).getTime();
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return result;
  }, [documents, search, sortKey, sortDir]);

  const allSelected =
    filtered.length > 0 &&
    filtered.every((d) => selectedIds.has(d.document_id));

  const toggleAll = useCallback(() => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filtered.map((d) => d.document_id)));
    }
  }, [allSelected, filtered]);

  const toggleOne = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const handleBulkRemove = useCallback(() => {
    if (!confirm(`Remove ${selectedIds.size} document(s) from the project?`))
      return;
    selectedIds.forEach((id) => onRemove(id));
    setSelectedIds(new Set());
  }, [selectedIds, onRemove]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 rounded-xl border border-dashed border-border">
        <FileText className="h-10 w-10 text-muted-foreground/40 mb-3" />
        <p className="text-sm font-medium text-muted-foreground">
          No documents yet
        </p>
        <p className="text-xs text-muted-foreground/60 mt-1">
          Add documents from the Documents page
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search documents..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 h-9 text-sm"
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
        <Select
          value={`${sortKey}-${sortDir}`}
          onValueChange={(v) => {
            const [k, d] = v.split('-') as [SortKey, SortDir];
            setSortKey(k);
            setSortDir(d);
          }}
        >
          <SelectTrigger className="w-[160px] h-9 text-sm">
            <ArrowUpDown className="h-3.5 w-3.5 mr-2 text-muted-foreground" />
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="added_at-desc">Newest first</SelectItem>
            <SelectItem value="added_at-asc">Oldest first</SelectItem>
            <SelectItem value="title-asc">Name A-Z</SelectItem>
            <SelectItem value="title-desc">Name Z-A</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Bulk action bar */}
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg bg-primary/10 border border-primary/20 px-4 py-2.5">
          <span className="text-sm font-medium text-primary">
            {selectedIds.size} selected
          </span>
          <div className="flex-1" />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSelectedIds(new Set())}
            className="text-muted-foreground hover:text-foreground text-xs"
            aria-label="Clear selection"
          >
            Clear
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleBulkRemove}
            className="text-destructive hover:text-destructive hover:bg-destructive/10 text-xs"
            aria-label={`Remove ${selectedIds.size} selected document${selectedIds.size !== 1 ? 's' : ''}`}
          >
            <Trash2 className="h-3.5 w-3.5 mr-1.5" />
            Remove
          </Button>
        </div>
      )}

      {/* Column header */}
      <div className="flex items-center gap-3 px-4 py-2 text-xs text-muted-foreground">
        <Checkbox
          checked={allSelected}
          onCheckedChange={toggleAll}
          aria-label="Select all documents"
        />
        <span className="flex-1">Document</span>
        <span className="w-24 text-right hidden sm:block">Status</span>
        <span className="w-24 text-right hidden sm:block">Added</span>
        <span className="w-10" />
      </div>

      {/* Document rows */}
      <div className="space-y-1">
        {filtered.map((doc) => {
          const status =
            statusConfig[(doc.document?.status || '').toLowerCase()];
          return (
            <div
              key={doc.id}
              className={`group flex items-center gap-3 rounded-lg border px-4 py-3 transition-all ${
                selectedIds.has(doc.document_id)
                  ? 'border-primary/30 bg-primary/5'
                  : 'border-border bg-card hover:bg-muted/30 hover:border-border'
              }`}
            >
              <Checkbox
                checked={selectedIds.has(doc.document_id)}
                onCheckedChange={() => toggleOne(doc.document_id)}
                aria-label={`Select ${doc.document?.title || 'document'}`}
              />
              <div className="text-muted-foreground shrink-0">
                {getFileIcon(doc.document?.filename)}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground truncate">
                  {doc.document?.title || doc.document?.filename || 'Untitled'}
                </p>
                {doc.document?.filename && doc.document?.title && (
                  <p className="text-xs text-muted-foreground truncate font-mono">
                    {doc.document.filename}
                  </p>
                )}
              </div>
              <div className="w-24 text-right shrink-0 hidden sm:block">
                {status ? (
                  <Badge variant={status.variant} className="text-[10px]">
                    {status.label}
                  </Badge>
                ) : (
                  <span className="text-xs text-muted-foreground">
                    {doc.document?.status || '\u2014'}
                  </span>
                )}
              </div>
              <div className="w-24 text-right shrink-0 hidden sm:block">
                <span className="text-xs text-muted-foreground">
                  {formatRelativeTime(
                    doc.added_at ||
                      doc.document?.created_at ||
                      new Date().toISOString()
                  )}
                </span>
              </div>
              <div className="w-10 shrink-0 flex justify-end">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <IconButton
                      icon={<MoreHorizontal className="h-4 w-4" />}
                      label="Document actions"
                      variant="ghost"
                      className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                    />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onClick={() =>
                        window.open(`/documents/${doc.document_id}`, '_blank')
                      }
                    >
                      <ExternalLink className="h-4 w-4 mr-2" />
                      View document
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        if (confirm('Remove this document from the project?')) {
                          onRemove(doc.document_id);
                        }
                      }}
                      className="text-destructive focus:text-destructive"
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      Remove from project
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          );
        })}
      </div>

      {/* Search no results */}
      {search && filtered.length === 0 && (
        <div className="text-center py-8">
          <p className="text-sm text-muted-foreground">
            No documents matching &quot;{search}&quot;
          </p>
        </div>
      )}
    </div>
  );
}
