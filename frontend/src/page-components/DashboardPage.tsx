import React from 'react';
import Link from 'next/link';

/**
 * Main Dashboard Page
 *
 * This is a simplified dashboard that redirects to the main upload functionality.
 * The core interface has been moved to app/page.tsx for Next.js App Router compatibility.
 */
export const DashboardPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-foreground mb-4">
            Multimodal Enterprise RAG System
          </h1>
          <p className="text-xl text-foreground max-w-3xl mx-auto">
            Upload documents to extract entities, build knowledge graphs, and
            enable intelligent search across your organization's knowledge base
          </p>
        </div>

        {/* Main Content */}
        <div className="text-center">
          <div className="bg-white rounded-lg shadow p-8">
            <h2 className="text-2xl font-semibold text-foreground mb-4">
              Document Upload
            </h2>
            <p className="text-foreground mb-6">
              Get started by uploading documents to process them with our
              AI-powered knowledge graph system.
            </p>
            <Link
              href="/documents/upload"
              className="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              Go to Document Upload
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
