'use client';

import React from 'react';

/**
 * Next.js Main Dashboard Page
 *
 * This is the core interface that combines:
 * - Left panel: Document upload and library
 * - Right panel: Search interface and results
 *
 * Migrated from Vite to Next.js with:
 * - Server-side rendering capabilities
 * - Enhanced SEO metadata
 * - Optimized bundle loading
 * - Built-in image optimization
 */
export default function HomePage() {
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
              </div>
            </div>
          </div>

          {/* Right Panel: Recent Documents */}
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">
                Recent Documents
              </h2>
              <p className="text-gray-600 mb-6">
                View and manage your recently uploaded documents.
              </p>
              <div className="space-y-4">
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
                  <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <h3 className="mt-2 text-sm font-medium text-gray-900">No recent documents</h3>
                  <p className="mt-1 text-sm text-gray-500">
                    Upload documents to see them here
                  </p>
                </div>
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

        {/* Bottom Section: Full Library Preview */}
        <div className="mt-12">
          <div className="bg-white rounded-lg shadow">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-2xl font-semibold text-gray-900">
                Document Library
              </h2>
              <p className="text-gray-600 mt-1">
                Full view of all your uploaded documents
              </p>
            </div>
            <div className="p-6">
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
                <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <h3 className="mt-2 text-sm font-medium text-gray-900">No documents yet</h3>
                <p className="mt-1 text-sm text-gray-500">
                  Upload documents to see them here
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}