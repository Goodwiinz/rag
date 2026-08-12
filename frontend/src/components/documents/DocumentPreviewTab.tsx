'use client';

import React from 'react';
import { DocumentInlineViewer } from './DocumentInlineViewer';

interface DocumentPreviewTabProps {
  documentId: string;
  filename: string;
  /** Frontend `file_type` or backend `document_type`, whichever is present. */
  kind?: string;
  mimeType?: string;
}

/**
 * The document detail page's Preview tab: the shared inline viewer plus the
 * tab's vertical rhythm. All viewer behavior lives in DocumentInlineViewer,
 * which the chat artifact panel reuses without this spacing.
 */
export function DocumentPreviewTab(props: DocumentPreviewTabProps) {
  return (
    <div className="py-6">
      <DocumentInlineViewer {...props} />
    </div>
  );
}
