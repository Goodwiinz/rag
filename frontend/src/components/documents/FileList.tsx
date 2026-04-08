import React, { useState } from 'react';
import {
  DocumentIcon,
  EyeIcon,
  TrashIcon,
  ArrowDownTrayIcon,
  EllipsisHorizontalIcon,
  CalendarIcon,
  DocumentTextIcon,
  PhotoIcon,
  MusicalNoteIcon,
  VideoCameraIcon
} from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';
import { Document } from '@/types';
import { STATUS_COLORS } from '@/types/constants';
import { IconButtonSm } from '@/components/ui/icon-button';

export interface FileListProps {
  documents: Document[];
  isLoading?: boolean;
  onDocumentSelect?: (document: Document) => void;
  onDocumentDelete?: (document: Document) => void;
  onDocumentDownload?: (document: Document) => void;
  onDocumentPreview?: (document: Document) => void;
  selectedDocuments?: string[];
  onSelectionChange?: (selectedIds: string[]) => void;
  className?: string;
}

interface FileListItemProps {
  document: Document;
  isSelected?: boolean;
  onSelect?: (selected: boolean) => void;
  onPreview?: () => void;
  onDownload?: () => void;
  onDelete?: () => void;
  onClick?: () => void;
}

const FileListItem: React.FC<FileListItemProps> = ({
  document,
  isSelected = false,
  onSelect,
  onPreview,
  onDownload,
  onDelete,
  onClick,
}) => {
  const [showActions, setShowActions] = useState(false);

  const getFileIcon = (fileType?: string, size: 'sm' | 'md' = 'sm') => {
    const iconClass = size === 'sm' ? "h-4 w-4" : "h-6 w-6";

    switch (fileType) {
      case 'application/pdf':
        return <DocumentTextIcon className={cn(iconClass, "text-red-600")} />;
      case 'text/plain':
        return <DocumentIcon className={cn(iconClass, "text-blue-600")} />;
      case 'image/jpeg':
      case 'image/png':
        return <PhotoIcon className={cn(iconClass, "text-green-600")} />;
      case 'audio/mpeg':
        return <MusicalNoteIcon className={cn(iconClass, "text-purple-600")} />;
      case 'video/mp4':
        return <VideoCameraIcon className={cn(iconClass, "text-orange-600")} />;
      default:
        return <DocumentIcon className={cn(iconClass, "text-gray-600")} />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'queued': return STATUS_COLORS.queued;
      case 'processing': return STATUS_COLORS.processing;
      case 'indexed': return STATUS_COLORS.indexed;
      case 'failed': return STATUS_COLORS.failed;
      default: return 'text-gray-500';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'queued': return 'Queued';
      case 'processing': return 'Processing';
      case 'indexed': return 'Indexed';
      case 'failed': return 'Failed';
      default: return 'Unknown';
    }
  };

  const formatFileSize = (bytes?: number): string => {
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString?: string): string => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div
      className={cn(
        "group bg-card border rounded-lg p-4 hover:bg-accent/50 transition-colors cursor-pointer",
        isSelected && "ring-2 ring-primary bg-primary/5"
      )}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
      onClick={onClick}
    >
      <div className="flex items-start space-x-3">
        {/* Checkbox */}
        {onSelect && (
          <div className="pt-1">
            <input
              type="checkbox"
              checked={isSelected}
              onChange={(e) => {
                e.stopPropagation();
                onSelect(e.target.checked);
              }}
              className="h-4 w-4 text-primary border-gray-300 rounded focus:ring-primary"
            />
          </div>
        )}

        {/* File Icon/Thumbnail */}
        <div className="flex-shrink-0">
          {document.thumbnail_url ? (
            <img
              src={document.thumbnail_url}
              alt={document.title}
              className="h-12 w-12 object-cover rounded"
            />
          ) : (
            <div className="h-12 w-12 bg-muted rounded flex items-center justify-center">
              {getFileIcon(document.file_type, 'md')}
            </div>
          )}
        </div>

        {/* File Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-medium text-foreground truncate">
                {document.title}
              </h3>
              <p className="text-xs text-muted-foreground truncate">
                {document.filename}
              </p>

              <div className="mt-1 flex items-center space-x-4 text-xs text-muted-foreground">
                <span>{formatFileSize(document.file_size)}</span>
                <span>•</span>
                <div className="flex items-center space-x-1">
                  <div
                    className={cn(
                      "w-2 h-2 rounded-full",
                      document.processing_status === 'processing' && "animate-pulse"
                    )}
                    style={{ backgroundColor: getStatusColor(document.processing_status) }}
                  />
                  <span>{getStatusText(document.processing_status)}</span>
                </div>
                <span>•</span>
                <span className="flex items-center space-x-1">
                  <CalendarIcon className="h-3 w-3" />
                  <span>{formatDate(document.upload_timestamp)}</span>
                </span>
              </div>

              {/* Additional metadata */}
              {(document.page_count || document.duration_seconds) && (
                <div className="mt-1 flex items-center space-x-3 text-xs text-muted-foreground">
                  {document.page_count && (
                    <span>{document.page_count} pages</span>
                  )}
                  {document.duration_seconds && (
                    <span>{Math.floor(document.duration_seconds / 60)}:{(document.duration_seconds % 60).toString().padStart(2, '0')}</span>
                  )}
                </div>
              )}

              {/* Processing error */}
              {document.processing_error && (
                <div className="mt-2 text-xs text-destructive bg-destructive/10 p-2 rounded">
                  Error: {document.processing_error}
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className={cn(
              "flex items-center space-x-1 opacity-0 transition-opacity",
              showActions && "opacity-100"
            )}>
              {onPreview && (
                <IconButtonSm
                  onClick={(e) => {
                    e.stopPropagation();
                    onPreview();
                  }}
                  className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-accent rounded"
                  label="Preview"
                  icon={<EyeIcon className="h-4 w-4" />}
                />
              )}

              {onDownload && (
                <IconButtonSm
                  onClick={(e) => {
                    e.stopPropagation();
                    onDownload();
                  }}
                  className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-accent rounded"
                  label="Download"
                  icon={<ArrowDownTrayIcon className="h-4 w-4" />}
                />
              )}

              {onDelete && (
                <IconButtonSm
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete();
                  }}
                  className="p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded"
                  label="Delete"
                  icon={<TrashIcon className="h-4 w-4" />}
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export const FileList: React.FC<FileListProps> = ({
  documents,
  isLoading = false,
  onDocumentSelect,
  onDocumentDelete,
  onDocumentDownload,
  onDocumentPreview,
  selectedDocuments = [],
  onSelectionChange,
  className,
}) => {
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');

  const handleSelectAll = (checked: boolean) => {
    const allIds = documents.map(doc => doc.id);
    onSelectionChange?.(checked ? allIds : []);
  };

  const handleDocumentSelect = (documentId: string, selected: boolean) => {
    if (selected) {
      onSelectionChange?.([...selectedDocuments, documentId]);
    } else {
      onSelectionChange?.(selectedDocuments.filter(id => id !== documentId));
    }
  };

  const handleBulkDelete = () => {
    // This would typically open a confirmation dialog
    const docsToDelete = documents.filter(doc => selectedDocuments.includes(doc.id));
    docsToDelete.forEach(doc => onDocumentDelete?.(doc));
    onSelectionChange?.([]);
  };

  const sortedDocuments = [...documents].sort((a, b) => {
    const dateA = a.upload_timestamp;
    const dateB = b.upload_timestamp;
    const timeA = dateA ? new Date(dateA).getTime() : 0;
    const timeB = dateB ? new Date(dateB).getTime() : 0;
    const safeTimeA = Number.isFinite(timeA) ? timeA : 0;
    const safeTimeB = Number.isFinite(timeB) ? timeB : 0;

    if (safeTimeB !== safeTimeA) {
      return safeTimeB - safeTimeA;
    }

    return (a.id ?? '').localeCompare(b.id ?? '');
  });

  if (isLoading) {
    return (
      <div className={cn("space-y-3", className)}>
        {[...Array(5)].map((_, index) => (
          <div key={index} className="bg-card border rounded-lg p-4 animate-pulse">
            <div className="flex items-center space-x-3">
              <div className="h-12 w-12 bg-muted rounded"></div>
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-muted rounded w-3/4"></div>
                <div className="h-3 bg-muted rounded w-1/2"></div>
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className={cn("text-center py-12", className)}>
        <DocumentIcon className="mx-auto h-12 w-12 text-muted-foreground" />
        <h3 className="mt-2 text-sm font-medium text-foreground">No documents</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Get started by uploading your first document.
        </p>
      </div>
    );
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Header with controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <h2 className="text-lg font-medium text-foreground">
            Documents ({documents.length})
          </h2>

          {onSelectionChange && (
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={selectedDocuments.length === documents.length && documents.length > 0}
                onChange={(e) => handleSelectAll(e.target.checked)}
                className="h-4 w-4 text-primary border-gray-300 rounded focus:ring-primary"
              />
              <span className="text-sm text-muted-foreground">
                {selectedDocuments.length > 0
                  ? `${selectedDocuments.length} selected`
                  : 'Select all'
                }
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center space-x-2">
          {/* View mode toggle */}
          <div className="flex items-center bg-muted rounded-md p-1">
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                "px-2 py-1 text-xs font-medium rounded transition-colors",
                viewMode === 'list'
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              List
            </button>
            <button
              onClick={() => setViewMode('grid')}
              className={cn(
                "px-2 py-1 text-xs font-medium rounded transition-colors",
                viewMode === 'grid'
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              Grid
            </button>
          </div>

          {/* Bulk actions */}
          {selectedDocuments.length > 0 && (
            <div className="flex items-center space-x-2">
              <button
                onClick={handleBulkDelete}
                className="px-3 py-1 text-xs font-medium text-destructive hover:bg-destructive/10 rounded transition-colors"
              >
                Delete ({selectedDocuments.length})
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Documents list/grid */}
      {viewMode === 'list' ? (
        <div className="space-y-2">
          {sortedDocuments.map((document) => (
            <FileListItem
              key={document.id}
              document={document}
              isSelected={selectedDocuments.includes(document.id)}
              onSelect={(selected) => handleDocumentSelect(document.id, selected)}
              onPreview={() => onDocumentPreview?.(document)}
              onDownload={() => onDocumentDownload?.(document)}
              onDelete={() => onDocumentDelete?.(document)}
              onClick={() => onDocumentSelect?.(document)}
            />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sortedDocuments.map((document) => (
            <FileListItem
              key={document.id}
              document={document}
              isSelected={selectedDocuments.includes(document.id)}
              onSelect={(selected) => handleDocumentSelect(document.id, selected)}
              onPreview={() => onDocumentPreview?.(document)}
              onDownload={() => onDocumentDownload?.(document)}
              onDelete={() => onDocumentDelete?.(document)}
              onClick={() => onDocumentSelect?.(document)}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default FileList;
