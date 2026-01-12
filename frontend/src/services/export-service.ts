/**
 * Export service for thread/conversation export functionality.
 * 
 * Handles API calls for:
 * - Single thread export (Markdown, PDF, JSON, HTML)
 * - Batch thread export with ZIP packaging
 * - Export format metadata
 */

import { api } from './api-client';

export type ExportFormat = 'markdown' | 'pdf' | 'json' | 'html';

export interface ExportOptions {
  includeSystemMessages?: boolean;
  includeCitations?: boolean;
  includeMetadata?: boolean;
  includeFeedback?: boolean;
}

export interface ExportFormatInfo {
  id: ExportFormat;
  name: string;
  extension: string;
  contentType: string;
  description: string;
}

export interface ExportPreview {
  threadId: string;
  title: string | null;
  format: ExportFormat;
  messageCount: number;
  citationCount: number;
  estimatedSizeBytes: number;
  exportable: boolean;
}

export interface BatchExportRequest {
  threadIds: string[];
  format: ExportFormat;
  options?: ExportOptions;
  asZip?: boolean;
}

/**
 * Export a single thread and trigger download.
 */
export async function exportThread(
  threadId: string,
  format: ExportFormat = 'markdown',
  options: ExportOptions = {}
): Promise<void> {
  const params = new URLSearchParams({
    format,
    include_system_messages: String(options.includeSystemMessages ?? false),
    include_citations: String(options.includeCitations ?? true),
    include_metadata: String(options.includeMetadata ?? true),
    include_feedback: String(options.includeFeedback ?? false),
  });

  const response = await fetch(
    `/api/v1/export/thread/${threadId}?${params.toString()}`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${localStorage.getItem('access_token')}`,
      },
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Export failed');
  }

  // Get filename from Content-Disposition header
  const disposition = response.headers.get('Content-Disposition');
  const filenameMatch = disposition?.match(/filename="(.+?)"/);
  const filename = filenameMatch?.[1] || `thread_export.${format === 'markdown' ? 'md' : format}`;

  // Download the file
  const blob = await response.blob();
  downloadBlob(blob, filename);
}

/**
 * Export multiple threads as a ZIP file.
 */
export async function exportBatch(request: BatchExportRequest): Promise<void> {
  const response = await fetch('/api/v1/export/batch', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${localStorage.getItem('access_token')}`,
    },
    body: JSON.stringify({
      thread_ids: request.threadIds,
      format: request.format,
      options: {
        include_system_messages: request.options?.includeSystemMessages ?? false,
        include_citations: request.options?.includeCitations ?? true,
        include_metadata: request.options?.includeMetadata ?? true,
        include_feedback: request.options?.includeFeedback ?? false,
      },
      as_zip: request.asZip ?? true,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Batch export failed');
  }

  const disposition = response.headers.get('Content-Disposition');
  const filenameMatch = disposition?.match(/filename="(.+?)"/);
  const filename = filenameMatch?.[1] || 'thread_export.zip';

  const blob = await response.blob();
  downloadBlob(blob, filename);
}

/**
 * Get available export formats.
 */
export async function getExportFormats(): Promise<{
  formats: ExportFormatInfo[];
  options: Record<string, string>;
  limits: { maxBatchSize: number; maxThreadMessages: number };
}> {
  const response = await api.get<{
    formats: ExportFormatInfo[];
    options: Record<string, string>;
    limits: { max_batch_size: number; max_thread_messages: number };
  }>('/export/formats');

  return {
    formats: response.formats,
    options: response.options,
    limits: {
      maxBatchSize: response.limits.max_batch_size,
      maxThreadMessages: response.limits.max_thread_messages,
    },
  };
}

/**
 * Preview export metadata before downloading.
 */
export async function previewExport(
  threadId: string,
  format: ExportFormat = 'markdown'
): Promise<ExportPreview> {
  const response = await api.post<{
    thread_id: string;
    title: string | null;
    format: string;
    message_count: number;
    citation_count: number;
    estimated_size_bytes: number;
    exportable: boolean;
  }>(`/export/preview/${threadId}?format=${format}`);

  return {
    threadId: response.thread_id,
    title: response.title,
    format: response.format as ExportFormat,
    messageCount: response.message_count,
    citationCount: response.citation_count,
    estimatedSizeBytes: response.estimated_size_bytes,
    exportable: response.exportable,
  };
}

/**
 * Helper function to download a blob as a file.
 */
function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Format file size for display.
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
