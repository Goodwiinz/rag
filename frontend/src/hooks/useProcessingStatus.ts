import { useState, useEffect, useCallback } from 'react';
import { Document } from '@/types';
import { useDocumentProcessingUpdates } from './useWebSocket';

interface ProcessingStatusData {
  jobId?: string;
  currentStep?: string;
  progress: number;
  estimatedRemainingSeconds?: number;
  error?: string;
  isProcessing: boolean;
}

export const useProcessingStatus = (document: Document) => {
  const [statusData, setStatusData] = useState<ProcessingStatusData>({
    progress: 0,
    isProcessing: false,
  });

  const { updates, clearUpdates } = useDocumentProcessingUpdates();

  // Find the most recent update for this document
  const getDocumentUpdate = useCallback(() => {
    return updates
      .filter(update => update.payload.document_id === document.id)
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())[0];
  }, [updates, document.id]);

  // Update status when document updates arrive
  useEffect(() => {
    const update = getDocumentUpdate();
    if (update) {
      const payload = update.payload;

      setStatusData(prev => ({
        ...prev,
        jobId: payload.job_id,
        currentStep: payload.current_step,
        progress: payload.progress,
        estimatedRemainingSeconds: payload.estimated_remaining_seconds,
        error: payload.error_message,
        isProcessing: payload.status !== 'indexed' && payload.status !== 'failed',
      }));
    }
  }, [getDocumentUpdate]);

  // Clear updates when document changes
  useEffect(() => {
    clearUpdates();
    setStatusData({
      progress: document.processing_status === 'indexed' ? 100 : 0,
      isProcessing: document.processing_status === 'processing' || document.processing_status === 'queued',
      error: document.processing_error,
    });
  }, [document.id, document.processing_status, document.processing_error, clearUpdates]);

  // Reset status data
  const resetStatus = useCallback(() => {
    setStatusData({
      progress: 0,
      isProcessing: false,
      error: undefined,
    });
  }, []);

  return {
    ...statusData,
    hasUpdates: updates.some(update => update.payload.document_id === document.id),
    resetStatus,
  };
};