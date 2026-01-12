/**
 * Export service for thread/conversation export functionality.
 * 
 * Handles API calls for:
 * - Single thread export (Markdown, PDF, JSON, HTML)
 * - Batch thread export with ZIP packaging
 * - Export format metadata
 */

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
  const response = await fetch('/api/v1/export/formats', {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${localStorage.getItem('access_token')}`,
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get export formats');
  }

  const data = await response.json();

  return {
    formats: data.formats,
    options: data.options,
    limits: {
      maxBatchSize: data.limits.max_batch_size,
      maxThreadMessages: data.limits.max_thread_messages,
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
  const response = await fetch(
    `/api/v1/export/preview/${threadId}?format=${format}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('access_token')}`,
      },
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Preview failed');
  }

  const data = await response.json();

  return {
    threadId: data.thread_id,
    title: data.title,
    format: data.format as ExportFormat,
    messageCount: data.message_count,
    citationCount: data.citation_count,
    estimatedSizeBytes: data.estimated_size_bytes,
    exportable: data.exportable,
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
