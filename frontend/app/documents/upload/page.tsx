/**
 * Document Upload Page
 * Simple and functional document upload interface
 */

'use client';

import { EnhancedDocumentUploadZone } from '@/components/documents/EnhancedDocumentUploadZone';
import { SimpleLayout } from '@/components/layout/SimpleLayout';
import { useState } from 'react';

export default function DocumentUploadPage() {
  const [uploadResults, setUploadResults] = useState<Array<{id: string, result: any}>>([]);

  const handleUploadComplete = (documentId: string, result: any) => {
    console.log('Upload completed:', { documentId, result });
    setUploadResults(prev => [...prev, { id: documentId, result }]);
  };

  const handleUploadError = (error: string, file: any) => {
    console.error('Upload error:', error, file);
  };

  return (
    <SimpleLayout>
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Document Upload
          </h1>
          <p className="text-gray-600">
            Upload documents to process them with our AI-powered knowledge graph system.
            Supports PDF, text files, images, audio, and video files.
          </p>
        </div>

        <EnhancedDocumentUploadZone
          onUploadComplete={handleUploadComplete}
          onUploadError={handleUploadError}
          maxFiles={10}
        />

        {uploadResults.length > 0 && (
          <div className="mt-8">
            <h2 className="text-xl font-semibold mb-4">Upload Results</h2>
            <div className="space-y-2">
              {uploadResults.map((result) => (
                <div key={result.id} className="p-4 bg-green-50 border border-green-200 rounded-lg">
                  <h3 className="font-medium text-green-800">
                    ✓ Upload Successful
                  </h3>
                  <p className="text-sm text-green-600 mt-1">
                    Document ID: {result.id}
                  </p>
                  <pre className="mt-2 text-xs text-gray-600 overflow-auto">
                    {JSON.stringify(result.result, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
    </SimpleLayout>
  );
}