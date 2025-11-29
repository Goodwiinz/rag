import React, { memo, useCallback, useMemo } from 'react';
import { useRealtimeProcessingStore } from '@/store/realtimeProcessingStore';
import { ProcessingOverview } from './ProcessingOverview';
import { DocumentQueueManager } from './DocumentQueueManager';
import { HistoricalProcessingData } from './HistoricalProcessingData';
import { ConnectionStatusBanner } from './ConnectionStatusBanner';
import { NotificationCenter } from './NotificationCenter';
import { DocumentProcessingState } from '@/types/realtime-processing';

interface DocumentProcessingDashboardProps {
  className?: string;
  showHistoricalData?: boolean;
  autoRefresh?: boolean;
  refreshInterval?: number;
  maxDocumentsPerPage?: number;
  enableCompactView?: boolean;
  showSystemMetrics?: boolean;
}

interface ProcessingDashboardConfig {
  layout: 'grid' | 'list' | 'tabs';
  visibleSections: {
    overview: boolean;
    queue: boolean;
    metrics: boolean;
    history: boolean;
    notifications: boolean;
  };
  refreshInterval: number;
  autoScroll: boolean;
  compactMode: boolean;
}

const DEFAULT_CONFIG: ProcessingDashboardConfig = {
  layout: 'tabs',
  visibleSections: {
    overview: true,
    queue: true,
    metrics: true,
    history: true,
    notifications: true,
  },
  refreshInterval: 500,
  autoScroll: true,
  compactMode: false,
};

export const DocumentProcessingDashboard: React.FC<DocumentProcessingDashboardProps> = memo(({
  className = '',
  showHistoricalData = true,
  autoRefresh = true,
  refreshInterval = 500,
  maxDocumentsPerPage = 50,
  enableCompactView = false,
}) => {
  const {
    queue,
    systemMetrics,
    notifications,
    ui,
    updatePreferences,
    setAutoScroll,
    setCompactView,
    getFilteredDocuments,
    getUnreadNotificationsCount,
  } = useRealtimeProcessingStore();

  // Update preferences if props change
  React.useEffect(() => {
    if (autoRefresh) {
      updatePreferences({ refreshInterval });
    }
    setAutoScroll(DEFAULT_CONFIG.autoScroll);
    if (enableCompactView) {
      setCompactView(true);
    }
  }, [autoRefresh, refreshInterval, enableCompactView, updatePreferences, setAutoScroll, setCompactView]);

  // Memoize filtered documents
  const filteredDocuments = useMemo(() => {
    return getFilteredDocuments();
  }, [getFilteredDocuments]);

  // Memoize unread notifications count
  const unreadCount = useMemo(() => {
    return getUnreadNotificationsCount();
  }, [getUnreadNotificationsCount]);

  // Handle layout change
  const handleLayoutChange = useCallback((layout: ProcessingDashboardConfig['layout']) => {
    // Store layout preference
    localStorage.setItem('dashboard-layout', layout);
  }, []);

  // Handle section visibility toggle
  const handleSectionToggle = useCallback((section: keyof ProcessingDashboardConfig['visibleSections']) => {
    // Update section visibility preference
    const currentConfig = localStorage.getItem('dashboard-config');
    const config = currentConfig ? JSON.parse(currentConfig) : DEFAULT_CONFIG;
    config.visibleSections[section] = !config.visibleSections[section];
    localStorage.setItem('dashboard-config', JSON.stringify(config));
  }, []);

  // Computed metrics
  const computedMetrics = useMemo(() => ({
    totalDocuments: queue.summary.total,
    activeDocuments: queue.summary.processing + queue.summary.queued,
    successRate: queue.metrics.successRate,
    averageProcessingTime: queue.metrics.averageProcessingTime,
    throughput: queue.metrics.throughput,
    failedDocuments: queue.summary.failed,
    memoryUsage: systemMetrics.memoryUsage,
    cpuUsage: systemMetrics.cpuUsage,
  }), [queue, systemMetrics]);

  if (!filteredDocuments.length && queue.summary.total === 0) {
    return (
      <div className={`flex flex-col items-center justify-center min-h-screen p-8 ${className}`}>
        <div className="text-center max-w-md">
          <div className="w-24 h-24 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center">
            <svg className="w-12 h-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">No documents in queue</h3>
          <p className="text-gray-600 mb-4">
            Upload some documents to see real-time processing status here.
          </p>
          <button className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
            Upload Documents
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`min-h-screen bg-gray-50 ${className}`}>
      {/* Connection Status Banner */}
      <ConnectionStatusBanner />

      {/* Main Dashboard Content */}
      <div className="container mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Document Processing</h1>
            <p className="text-gray-600">
              Real-time monitoring of document processing pipeline
            </p>
          </div>

          <div className="flex items-center space-x-4">
            {/* Quick Stats */}
            <div className="flex items-center space-x-6 text-sm">
              <div className="flex items-center">
                <div className="w-2 h-2 bg-green-500 rounded-full mr-2"></div>
                <span className="text-gray-600">
                  {queue.summary.processing} Processing
                </span>
              </div>
              <div className="flex items-center">
                <div className="w-2 h-2 bg-yellow-500 rounded-full mr-2"></div>
                <span className="text-gray-600">
                  {queue.summary.queued} Queued
                </span>
              </div>
              <div className="flex items-center">
                <div className="w-2 h-2 bg-blue-500 rounded-full mr-2"></div>
                <span className="text-gray-600">
                  {queue.summary.completed} Completed
                </span>
              </div>
            </div>

            {/* Notification Bell */}
            <div className="relative">
              <button className="p-2 text-gray-600 hover:text-gray-900 relative">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
                {unreadCount > 0 && (
                  <span className="absolute top-0 right-0 -mt-1 -mr-1 px-2 py-1 text-xs font-bold text-white bg-red-500 rounded-full">
                    {unreadCount}
                  </span>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Processing Overview */}
        <div className="mb-6">
          <ProcessingOverview
            metrics={computedMetrics}
            documents={filteredDocuments}
            systemMetrics={systemMetrics}
          />
        </div>

        {/* Main Content Area */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Document Queue Manager - Takes up 2/3 of the width */}
          <div className="lg:col-span-2">
            <DocumentQueueManager
              documents={filteredDocuments}
              pagination={queue.pagination}
              filters={queue.filters}
              selectedDocuments={ui.selectedDocuments}
              onFiltersChange={(filters) => {/* Handle filter changes */}}
              onPaginationChange={(pagination) => {/* Handle pagination changes */}}
              maxDocumentsPerPage={maxDocumentsPerPage}
              compactView={ui.compactView}
              autoScroll={ui.autoScrollEnabled}
            />
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Historical Processing Data */}
            {showHistoricalData && (
              <HistoricalProcessingData
                metrics={queue.metrics}
                systemMetrics={systemMetrics}
                compact={ui.compactView}
              />
            )}

            {/* NotificationCenter */}
            {notifications.length > 0 && (
              <NotificationCenter
                notifications={notifications}
                maxVisible={5}
                compact={ui.compactView}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
});

DocumentProcessingDashboard.displayName = 'DocumentProcessingDashboard';