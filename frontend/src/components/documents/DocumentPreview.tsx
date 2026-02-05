import React, { useState, useCallback } from 'react';
import {
  XMarkIcon,
  DocumentTextIcon,
  PhotoIcon,
  MusicalNoteIcon,
  VideoCameraIcon,
  ArrowDownTrayIcon,
  ShareIcon,
  EyeIcon,
  InformationCircleIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  PencilIcon,
} from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';
import { Document } from '@/types';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ProcessingStatus } from './ProcessingStatus';
import { apiClient } from '@/services/api';

interface DocumentPreviewProps {
  document: Document | null;
  isOpen: boolean;
  onClose: () => void;
  onDownload?: (document: Document) => void;
  onShare?: (document: Document) => void;
  onEditMetadata?: (document: Document) => void;
}

export const DocumentPreview: React.FC<DocumentPreviewProps> = ({
  document,
  isOpen,
  onClose,
  onDownload,
  onShare,
  onEditMetadata,
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [localDocument, setLocalDocument] = useState<Document | null>(document);

  // Update local document when prop changes
  React.useEffect(() => {
    setLocalDocument(document);
  }, [document]);

  const handleRetry = useCallback(async () => {
    if (!localDocument || isRetrying) return;

    setIsRetrying(true);
    try {
      // Call backend endpoint to requeue/reprocess the document
      const response = await fetch(`/api/documents/${localDocument.id}/reprocess`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to queue document for reprocessing');
      }

      // Optimistic update: set status to queued
      setLocalDocument(prev => prev ? { ...prev, processing_status: 'queued', processing_error: undefined } : null);

      toast.success('Document queued for reprocessing');
    } catch (error) {
      console.error('Failed to reprocess document:', error);
      toast.error('Failed to queue document for reprocessing. Please try again.');
    } finally {
      setIsRetrying(false);
    }
  }, [localDocument, isRetrying]);

  const getFileIcon = () => {
    const iconClass = "h-8 w-8";
    switch (document?.file_type) {
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
    switch (document?.processing_status) {
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
    switch (document?.processing_status) {
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

  const formatFileSize = (bytes: number | undefined): string => {
    if (bytes === undefined || bytes === null) return '-';
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string | undefined): string => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getDurationDisplay = (): string => {
    if (document?.duration_seconds) {
      const minutes = Math.floor(document.duration_seconds / 60);
      const seconds = document.duration_seconds % 60;
      if (minutes > 0) {
        return `${minutes}:${seconds.toString().padStart(2, '0')}`;
      }
      return `${seconds}s`;
    }
    if (document?.page_count) {
      return `${document.page_count} pages`;
    }
    return '';
  };

  const handleDownload = useCallback(async () => {
    if (!document || !onDownload) return;

    setIsLoading(true);
    try {
      await onDownload(document);
    } catch (error) {
      console.error('Failed to download document:', error);
    } finally {
      setIsLoading(false);
    }
  }, [document, onDownload]);

  const handleShare = useCallback(() => {
    if (!document || !onShare) return;
    onShare(document);
  }, [document, onShare]);

  const renderPreviewContent = () => {
    if (!document) return null;

    // For images, show thumbnail
    if (document.file_type === 'jpg' || document.file_type === 'png') {
      return (
        <div className="flex items-center justify-center bg-gray-50 rounded-lg p-4">
          {document.thumbnail_url ? (
            <img
              src={document.thumbnail_url}
              alt={document.title}
              className="max-w-full max-h-96 object-contain rounded-lg shadow-lg"
            />
          ) : (
            <div className="text-center">
              <PhotoIcon className="h-16 w-16 text-gray-400 mx-auto mb-2" />
              <p className="text-gray-500">No preview available</p>
            </div>
          )}
        </div>
      );
    }

    // For PDFs and text files, show placeholder
    if (document.file_type === 'pdf' || document.file_type === 'txt') {
      return (
        <div className="flex items-center justify-center bg-gray-50 rounded-lg p-8">
          <div className="text-center">
            <DocumentTextIcon className="h-16 w-16 text-gray-400 mx-auto mb-4" />
            <p className="text-lg font-medium text-gray-700 mb-2">{document.title}</p>
            <p className="text-gray-500 mb-4">
              {document.page_count ? `${document.page_count} pages` : 'Document preview'}
            </p>
            <Button onClick={handleDownload} disabled={isLoading} variant="outline">
              <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
              {isLoading ? 'Downloading...' : 'Download to view'}
            </Button>
          </div>
        </div>
      );
    }

    // For audio files
    if (document.file_type === 'mp3') {
      return (
        <div className="flex items-center justify-center bg-gray-50 rounded-lg p-8">
          <div className="text-center">
            <MusicalNoteIcon className="h-16 w-16 text-gray-400 mx-auto mb-4" />
            <p className="text-lg font-medium text-gray-700 mb-2">{document.title}</p>
            <p className="text-gray-500 mb-4">
              {getDurationDisplay() || 'Audio file'}
            </p>
            <Button onClick={handleDownload} disabled={isLoading} variant="outline">
              <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
              {isLoading ? 'Downloading...' : 'Download audio'}
            </Button>
          </div>
        </div>
      );
    }

    // For video files
    if (document.file_type === 'mp4') {
      return (
        <div className="flex items-center justify-center bg-gray-50 rounded-lg p-8">
          <div className="text-center">
            <VideoCameraIcon className="h-16 w-16 text-gray-400 mx-auto mb-4" />
            <p className="text-lg font-medium text-gray-700 mb-2">{document.title}</p>
            <p className="text-gray-500 mb-4">
              {getDurationDisplay() || 'Video file'}
            </p>
            <Button onClick={handleDownload} disabled={isLoading} variant="outline">
              <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
              {isLoading ? 'Downloading...' : 'Download video'}
            </Button>
          </div>
        </div>
      );
    }

    // Default fallback
    return (
      <div className="flex items-center justify-center bg-gray-50 rounded-lg p-8">
        <div className="text-center">
          <DocumentTextIcon className="h-16 w-16 text-gray-400 mx-auto mb-4" />
          <p className="text-lg font-medium text-gray-700 mb-2">{document.title}</p>
          <p className="text-gray-500 mb-4">Preview not available for this file type</p>
          <Button onClick={handleDownload} disabled={isLoading} variant="outline">
            <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
            {isLoading ? 'Downloading...' : 'Download file'}
          </Button>
        </div>
      </div>
    );
  };

  if (!document || !isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-full items-center justify-center p-4">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black bg-opacity-25 transition-opacity"
          onClick={onClose}
        />

        {/* Modal */}
        <div className="relative w-full max-w-4xl bg-white rounded-xl shadow-2xl">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b">
            <div className="flex items-center space-x-4">
              {getFileIcon()}
              <div>
                <h2 className="text-xl font-semibold text-gray-900">
                  {document.title}
                </h2>
                <p className="text-sm text-gray-500">{document.filename}</p>
              </div>
            </div>
            <Button
              onClick={onClose}
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
            >
              <XMarkIcon className="h-5 w-5" />
            </Button>
          </div>

          {/* Content */}
          <div className="p-6">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Preview Area */}
              <div className="lg:col-span-2">
                <div className="mb-4">
                  <h3 className="text-lg font-medium text-gray-900 mb-2">Preview</h3>
                </div>
                {renderPreviewContent()}
              </div>

              {/* Details Sidebar */}
              <div className="space-y-6">
                {/* File Information */}
                <div>
                  <h3 className="text-lg font-medium text-gray-900 mb-4">File Information</h3>
                  <div className="space-y-3">
                    <div>
                      <p className="text-sm font-medium text-gray-700">File Size</p>
                      <p className="text-sm text-gray-500">{formatFileSize(document.file_size)}</p>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-700">File Type</p>
                      <p className="text-sm text-gray-500">{(document.file_type ?? document.document_type ?? '-').toUpperCase()}</p>
                    </div>
                    {getDurationDisplay() && (
                      <div>
                        <p className="text-sm font-medium text-gray-700">Duration</p>
                        <p className="text-sm text-gray-500">{getDurationDisplay()}</p>
                      </div>
                    )}
                    <div>
                      <p className="text-sm font-medium text-gray-700">Uploaded</p>
                      <p className="text-sm text-gray-500">{formatDate(document.upload_timestamp)}</p>
                    </div>
                  </div>
                </div>

                {/* Processing Status */}
                <div>
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Processing Status</h3>
                  <div className="space-y-3">
                    <div className="flex items-center space-x-2">
                      {getStatusIcon()}
                      <span className="text-sm text-gray-700">{getStatusText()}</span>
                    </div>
                    {document.processing_error && (
                      <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                        <p className="text-sm text-red-600">{document.processing_error}</p>
                      </div>
                    )}
                    {(document.processing_status === 'processing' || document.processing_status === 'queued' || document.processing_status === 'failed') && (
                      <ProcessingStatus
                        document={localDocument || document}
                        compact
                        onRetry={document.processing_status === 'failed' ? handleRetry : undefined}
                      />
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div>
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Actions</h3>
                  <div className="space-y-2">
                    <Button
                      onClick={handleDownload}
                      disabled={isLoading}
                      className="w-full"
                      variant="outline"
                    >
                      <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
                      {isLoading ? 'Downloading...' : 'Download'}
                    </Button>
                    {onEditMetadata && (
                      <Button
                        onClick={() => onEditMetadata(document)}
                        className="w-full"
                        variant="outline"
                      >
                        <PencilIcon className="h-4 w-4 mr-2" />
                        Edit Metadata
                      </Button>
                    )}
                    {onShare && (
                      <Button
                        onClick={handleShare}
                        className="w-full"
                        variant="outline"
                      >
                        <ShareIcon className="h-4 w-4 mr-2" />
                        Share
                      </Button>
                    )}
                  </div>
                </div>

                {/* Metadata */}
                {document.metadata && Object.keys(document.metadata).length > 0 && (
                  <div>
                    <h3 className="text-lg font-medium text-gray-900 mb-4">Metadata</h3>
                    <div className="space-y-2">
                      {Object.entries(document.metadata).map(([key, value]) => (
                        <div key={key}>
                          <p className="text-sm font-medium text-gray-700 capitalize">
                            {key.replace(/_/g, ' ')}
                          </p>
                          <p className="text-sm text-gray-500">{String(value)}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DocumentPreview;