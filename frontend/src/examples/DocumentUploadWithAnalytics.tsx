/**
 * Example: Document Upload with Analytics Tracking
 * Shows how to integrate analytics into document upload functionality
 */

'use client';

import { useState } from 'react';
import {
  useDocumentAnalytics,
  useUIAnalytics,
} from '@/hooks/useAnalyticsTracking';
import { DocumentUploadZone } from '@/components/documents/DocumentUploadZone';

export default function DocumentUploadWithAnalytics() {
  const [uploadResults, setUploadResults] = useState<
    Array<{ id: string; result: any }>
  >([]);

  // Initialize analytics hooks
  const {
    trackUpload,
    trackProcessingStart,
    trackProcessingComplete,
    trackProcessingError,
  } = useDocumentAnalytics();
  const { trackClick, trackFormSubmit } = useUIAnalytics();

  const handleUploadStart = (files: File[]) => {
    // Track upload start event
    files.forEach((file) => {
      trackUpload(file.type.split('/')[1] || 'unknown', file.size, false);
    });

    // Track UI interaction
    trackClick('upload_zone', {
      fileCount: files.length,
      totalSize: files.reduce((sum, f) => sum + f.size, 0),
    });
  };

  const handleUploadComplete = (documentId: string, result: any) => {
    console.log('Upload completed:', { documentId, result });
    setUploadResults((prev) => [...prev, { id: documentId, result }]);

    // Track successful upload
    if (result.file) {
      trackUpload(
        result.file.type.split('/')[1] || 'unknown',
        result.file.size || 0,
        true
      );
    }

    // Track processing completion if duration is available
    if (result.processingDuration) {
      trackProcessingComplete(documentId, result.processingDuration);
    }

    // Track successful form submission
    trackFormSubmit('document_upload', true);
  };

  const handleUploadError = (error: string, file: any) => {
    console.error('Upload error:', error, file);

    // Track upload failure
    if (file) {
      trackUpload(file.type.split('/')[1] || 'unknown', file.size || 0, false);
    }

    // Track processing error
    trackProcessingError(file?.id || 'unknown', new Error(error));

    // Track failed form submission
    trackFormSubmit('document_upload', false, [error]);
  };

  const handleProcessingStart = (documentId: string) => {
    // Track when document processing begins
    trackProcessingStart(documentId);
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-foreground mb-2">
            Document Upload
          </h1>
          <p className="text-foreground">
            Upload documents to process them with our AI-powered knowledge graph
            system. Supports PDF, text files, images, audio, and video files.
          </p>
        </div>

        <DocumentUploadZone
          onUploadStart={handleUploadStart}
          onUploadComplete={handleUploadComplete}
          onUploadError={handleUploadError}
          onProcessingStart={handleProcessingStart}
          maxFiles={10}
        />

        {uploadResults.length > 0 && (
          <div className="mt-8">
            <h2 className="text-xl font-semibold mb-4">Upload Results</h2>
            <div className="space-y-2">
              {uploadResults.map((result) => (
                <div
                  key={result.id}
                  className="p-4 bg-green-50 border border-green-200 rounded-lg"
                >
                  <h3 className="font-medium text-green-800">
                    ✓ Upload Successful
                  </h3>
                  <p className="text-sm text-green-600 mt-1">
                    Document ID: {result.id}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
