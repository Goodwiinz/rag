import React from 'react';
import { TwoPanelLayout } from '@/components/layout/TwoPanelLayout';
import { DocumentUploadZone } from '@/components/documents/DocumentUploadZone';
import { DocumentLibrary } from '@/components/documents/DocumentLibrary';
import { QueryInterface } from '@/components/search/QueryInterface';
import { ResultsDisplay } from '@/components/search/ResultsDisplay';

/**
 * Main Dashboard Page
 *
 * This is the core interface that combines:
 * - Left panel: Document upload and library
 * - Right panel: Search interface and results
 */
export const DashboardPage: React.FC = () => {
  return (
    <div className="h-full">
      <TwoPanelLayout
        leftPanel={
          <div className="flex flex-col h-full gap-6">
            {/* Document Upload Zone */}
            <DocumentUploadZone />

            {/* Document Library */}
            <DocumentLibrary />
          </div>
        }
        rightPanel={
          <div className="flex flex-col h-full">
            {/* Search Interface */}
            <QueryInterface />

            {/* Results Display */}
            <ResultsDisplay />
          </div>
        }
      />
    </div>
  );
};

export default DashboardPage;