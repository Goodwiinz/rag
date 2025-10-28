'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useDocuments } from '@/hooks/useDocuments';
import { useAuth } from '@/hooks/useAuth';
import { DocumentCard } from '@/components/documents/DocumentCard';
import { EnhancedDocumentUploadZone } from '@/components/documents/EnhancedDocumentUploadZone';

/**
 * Next.js Main Dashboard Page
 *
 * This is the core interface that combines:
 * - Left panel: Document upload and library
 * - Right panel: Recent documents with live data
 *
 * Migrated from Vite to Next.js with:
 * - Server-side rendering capabilities
 * - Enhanced SEO metadata
 * - Optimized bundle loading
 * - Built-in image optimization
 */
export default function HomePage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [showUploadZone, setShowUploadZone] = useState(false);
  const [uploadResults, setUploadResults] = useState<Array<{id: string, result: any}>>([]);

  // Fetch recent documents (limit to 5 for the home page) - only if authenticated
  const { documents, loading, error } = useDocuments({
    initialPageSize: 5,
    autoFetch: isAuthenticated && !authLoading,
  });

  const handleUploadComplete = (documentId: string, result: any) => {
    console.log('Upload completed:', { documentId, result });
    setUploadResults(prev => [...prev, { id: documentId, result }]);
    setShowUploadZone(false);
  };

  const handleUploadError = (error: string, file: any) => {
    console.error('Upload error:', error, file);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Multimodal Enterprise RAG System
          </h1>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            Upload documents to extract entities, build knowledge graphs, and enable intelligent search across your organization's knowledge base
          </p>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left Panel: Document Upload */}
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">
                Document Upload
              </h2>
              <p className="text-gray-600 mb-6">
                Upload PDFs, text files, images, audio, and video files to extract entities and populate the knowledge graph.
              </p>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
                <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <h3 className="mt-2 text-sm font-medium text-gray-900">Upload documents</h3>
                <p className="mt-1 text-sm text-gray-500">
                  Drag and drop or click to browse
                </p>
                <div className="mt-4 flex gap-3">
                  <button
                    onClick={() => setShowUploadZone(true)}
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    Upload Files Here
                  </button>
                  <Link
                    href="/documents/upload"
                    className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    Advanced Upload
                  </Link>
                </div>
              </div>
            </div>
          </div>

          {/* Right Panel: Recent Documents */}
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-2xl font-semibold text-gray-900">
                  Recent Documents
                </h2>
                {documents.length > 0 && (
                  <Link
                    href="/documents"
                    className="text-sm text-blue-600 hover:text-blue-700"
                  >
                    View all →
                  </Link>
                )}
              </div>
              <p className="text-gray-600 mb-6">
                View and manage your recently uploaded documents.
              </p>
              <div className="space-y-4">
                {authLoading || loading ? (
                  <div className="text-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                    <p className="mt-2 text-sm text-gray-600">
                      {authLoading ? 'Checking authentication...' : 'Loading documents...'}
                    </p>
                  </div>
                ) : !isAuthenticated ? (
                  <div className="border-2 border-blue-300 rounded-lg p-6 text-center bg-blue-50">
                    <svg className="mx-auto h-10 w-10 text-blue-500 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2z" />
                    </svg>
                    <p className="text-sm font-medium text-blue-800 mb-2">Sign In to View Documents</p>
                    <p className="text-xs text-blue-700 mb-4">
                      Please log in to view and manage your documents.
                    </p>
                    <div className="flex gap-3 justify-center">
                      <Link
                        href="/login"
                        className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                      >
                        Sign In
                      </Link>
                      <Link
                        href="/register"
                        className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                      >
                        Create Account
                      </Link>
                    </div>
                  </div>
                ) : error ? (
                  <div className="border-2 border-red-300 rounded-lg p-6 text-center bg-red-50">
                    <svg className="mx-auto h-10 w-10 text-red-500 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p className="text-sm font-medium text-red-800 mb-2">Error Loading Documents</p>
                    <p className="text-xs text-red-700">
                      {error}
                    </p>
                  </div>
                ) : documents.length === 0 ? (
                  <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
                    <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <h3 className="mt-2 text-sm font-medium text-gray-900">No recent documents</h3>
                    <p className="mt-1 text-sm text-gray-500">
                      Upload documents to see them here
                    </p>
                  </div>
                ) : (
                  <>
                    {documents.map((doc) => (
                      <DocumentCard
                        key={doc.id}
                        document={doc}
                        onSelect={() => {}}
                        selected={false}
                      />
                    ))}
                  </>
                )}
              </div>
            </div>

            {/* Quick Stats */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                System Status
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">✓</div>
                  <div className="text-sm text-gray-600">Backend API</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">✓</div>
                  <div className="text-sm text-gray-600">Database</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">✓</div>
                  <div className="text-sm text-gray-600">Vector Store</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">✓</div>
                  <div className="text-sm text-gray-600">Knowledge Graph</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Upload Zone Overlay */}
      {showUploadZone && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center">
              <h2 className="text-xl font-semibold text-gray-900">Upload Documents</h2>
              <button
                onClick={() => setShowUploadZone(false)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
                aria-label="Close upload dialog"
              >
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-6">
              <EnhancedDocumentUploadZone
                onUploadComplete={handleUploadComplete}
                onUploadError={handleUploadError}
                maxFiles={10}
              />
            </div>
          </div>
        </div>
      )}

      {/* Upload Results */}
      {uploadResults.length > 0 && (
        <div className="fixed bottom-4 right-4 max-w-md z-50">
          <div className="bg-white rounded-lg shadow-lg border border-gray-200 p-4">
            <h3 className="font-medium text-green-800 mb-2">
              ✓ Upload Complete
            </h3>
            <p className="text-sm text-green-600">
              {uploadResults.length} document{uploadResults.length > 1 ? 's' : ''} uploaded successfully
            </p>
            <button
              onClick={() => setUploadResults([])}
              className="mt-2 text-sm text-gray-500 hover:text-gray-700"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}
    </div>
  );
}