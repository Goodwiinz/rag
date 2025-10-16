import React, { useState } from 'react';
import {
  DocumentTextIcon,
  PhotoIcon,
  MusicalNoteIcon,
  VideoCameraIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  EyeIcon,
  TrashIcon,
  EllipsisHorizontalIcon,
  ArrowDownTrayIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import { Document } from '@/types';
import { cn } from '@/lib/utils';
import { ProcessingStatus } from './ProcessingStatus';

interface DocumentCardProps {
  document: Document;
  selected?: boolean;
  onSelect?: (documentId: string) => void;
  onPreview?: (document: Document) => void;
  onDelete?: (documentId: string) => void;
  onDownload?: (document: Document) => void;
  onRetry?: (documentId: string) => void;
  showProcessingStatus?: boolean;
  className?: string;
}

export const DocumentCard: React.FC<DocumentCardProps> = ({
  document,
  selected = false,
  onSelect,
  onPreview,
  onDelete,
  onDownload,
  onRetry,
  showProcessingStatus = true,
  className,
}) => {
  const [showActions, setShowActions] = useState(false);

  const getFileIcon = () => {
    const iconClass = "h-8 w-8";
    switch (document.file_type) {
      case 'pdf':
        return <DocumentTextIcon className={cn(iconClass, "text-red-600")} />;
      case 'txt':
        return <DocumentTextIcon className={cn(iconClass, "text-blue-600")} />;
      case 'jpg':
      case 'png':
        return <PhotoIcon className={cn(iconClass, "text-green-600")} />;
      case 'mp3':
        return <MusicalNoteIcon className={cn(iconClass, "text-purple-600")} />;
      case 'mp4':
        return <VideoCameraIcon className={cn(iconClass, "text-orange-600")} />;
      default:
        return <DocumentTextIcon className={cn(iconClass, "text-gray-600")} />;
    }
  };

  const getStatusIcon = () => {
    switch (document.processing_status) {
      case 'queued':
        return <ClockIcon className="h-4 w-4 text-yellow-600" />;
      case 'processing':
        return <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />;
      case 'indexed':
        return <CheckCircleIcon className="h-4 w-4 text-green-600" />;
      case 'failed':
        return <XCircleIcon className="h-4 w-4 text-red-600" />;
      default:
        return null;
    }
  };

  const getStatusText = () => {
    switch (document.processing_status) {
      case 'queued':
        return 'Queued for processing';
      case 'processing':
        return 'Processing...';
      case 'indexed':
        return 'Ready for search';
      case 'failed':
        return 'Processing failed';
      default:
        return 'Unknown status';
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const getDurationDisplay = (): string => {
    if (document.duration_seconds) {
      const minutes = Math.floor(document.duration_seconds / 60);
      const seconds = document.duration_seconds % 60;
      if (minutes > 0) {
        return `${minutes}:${seconds.toString().padStart(2, '0')}`;
      }
      return `${seconds}s`;
    }
    if (document.page_count) {
      return `${document.page_count} pages`;
    }
    return '';
  };

  const handleSelect = () => {
    onSelect?.(document.id);
  };

  const handlePreview = () => {
    onPreview?.(document);
  };

  const handleDelete = () => {
    onDelete?.(document.id);
  };

  const handleDownload = () => {
    onDownload?.(document);
  };

  return (
    <div
      className={cn(
        "relative bg-card border rounded-lg p-4 transition-all duration-200 hover:shadow-md",
        selected && "ring-2 ring-primary ring-offset-2",
        className
      )}
    >
      {/* Selection Checkbox */}
      <div className="absolute top-4 left-4">
        <button
          onClick={handleSelect}
          className={cn(
            "h-4 w-4 rounded border-2 transition-colors",
            selected
              ? "bg-primary border-primary"
              : "border-gray-300 hover:border-primary"
          )}
          aria-label={selected ? "Deselect document" : "Select document"}
        >
          {selected && (
            <svg
              className="h-3 w-3 text-white"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            </svg>
          )}
        </button>
      </div>

      {/* Document Info */}
      <div className="flex items-start space-x-4">
        {/* File Icon/Thumbnail */}
        <div className="flex-shrink-0">
          {document.thumbnail_url ? (
            <img
              src={document.thumbnail_url}
              alt={document.title}
              className="h-16 w-16 object-cover rounded-lg"
              loading="lazy"
            />
          ) : (
            <div className="h-16 w-16 bg-muted rounded-lg flex items-center justify-center">
              {getFileIcon()}
            </div>
          )}
        </div>

        {/* Document Details */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0 pr-2">
              <h3 className="text-sm font-medium text-foreground truncate mb-1">
                {document.title}
              </h3>
              <p className="text-xs text-muted-foreground truncate mb-2">
                {document.filename}
              </p>

              {/* Metadata */}
              <div className="flex items-center space-x-4 text-xs text-muted-foreground">
                <span>{formatFileSize(document.file_size)}</span>
                <span>{formatDate(document.upload_timestamp)}</span>
                {getDurationDisplay() && (
                  <span>{getDurationDisplay()}</span>
                )}
              </div>

              {/* Status */}
              <div className="flex items-center space-x-2 mt-2">
                {getStatusIcon()}
                <span className="text-xs text-muted-foreground">
                  {getStatusText()}
                </span>
                {document.processing_error && (
                  <span className="text-xs text-destructive">
                    • {document.processing_error}
                  </span>
                )}
              </div>
            </div>

            {/* Actions Menu */}
            <div className="relative">
              <button
                onClick={() => setShowActions(!showActions)}
                className="p-1 text-muted-foreground hover:text-foreground hover:bg-accent rounded transition-colors"
                aria-label="More options"
              >
                <EllipsisHorizontalIcon className="h-4 w-4" />
              </button>

              {showActions && (
                <div className="absolute right-0 top-full mt-1 w-48 bg-popover border rounded-md shadow-lg z-10">
                  <div className="py-1">
                    <button
                      onClick={handlePreview}
                      className="flex items-center w-full px-3 py-2 text-sm text-foreground hover:bg-accent transition-colors"
                    >
                      <EyeIcon className="h-4 w-4 mr-2" />
                      Preview
                    </button>
                    <button
                      onClick={handleDownload}
                      className="flex items-center w-full px-3 py-2 text-sm text-foreground hover:bg-accent transition-colors"
                    >
                      <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
                      Download
                    </button>
                    <button
                      onClick={handleDelete}
                      className="flex items-center w-full px-3 py-2 text-sm text-destructive hover:bg-destructive/10 transition-colors"
                    >
                      <TrashIcon className="h-4 w-4 mr-2" />
                      Delete
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Processing Status (for processing documents) */}
      {showProcessingStatus && (document.processing_status === 'processing' || document.processing_status === 'queued' || document.processing_status === 'failed') && (
        <div className="mt-4 pt-4 border-t">
          <ProcessingStatus
            document={document}
            compact
            onRetry={onRetry ? () => onRetry(document.id) : undefined}
          />
        </div>
      )}

      {/* Click outside to close actions menu */}
      {showActions && (
        <div
          className="fixed inset-0 z-0"
          onClick={() => setShowActions(false)}
        />
      )}
    </div>
  );
};

export default DocumentCard;