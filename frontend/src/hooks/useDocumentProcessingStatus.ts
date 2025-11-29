import { useState, useEffect, useCallback, useRef } from 'react';
import { useWebSocket } from './useWebSocket';
import { Document, DocumentProcessingUpdate } from '@/types';

/**
 * Parameters for useDocumentProcessingStatus hook
 */
export interface UseDocumentProcessingStatusParams {
  /** Document ID to track */
  documentId: string;
  /** Optional job ID for more specific filtering */
  jobId?: string;
  /** Enable/disable the subscription (default: true) */
  enabled?: boolean;
}

/**
 * Return type for useDocumentProcessingStatus hook
 */
export interface UseDocumentProcessingStatusReturn {
  /** Current processing progress (0-100) */
  progress: number;
  /** Current processing step name */
  currentStep: string;
  /** Error message if processing failed */
  error: string | null;
  /** Estimated remaining time in seconds */
  estimatedRemainingSeconds?: number;
  /** Whether WebSocket is connected */
  isConnected: boolean;
  /** Timestamp of last update */
  lastUpdate: Date | null;
  /** Current processing status */
  status: Document['processing_status'];
  /** Processing result if completed */
  result?: any;
}

/**
 * Custom hook to track document processing status via WebSocket
 *
 * Subscribes to real-time document processing updates and provides
 * current status, progress, and error information.
 *
 * @example
 * ```tsx
 * const processing = useDocumentProcessingStatus({
 *   documentId: document.id,
 *   enabled: document.processing_status === 'processing'
 * });
 *
 * return (
 *   <div>
 *     <p>Progress: {processing.progress}%</p>
 *     <p>Step: {processing.currentStep}</p>
 *     {!processing.isConnected && <p>Offline</p>}
 *   </div>
 * );
 * ```
 */
export function useDocumentProcessingStatus(
  params: UseDocumentProcessingStatusParams
): UseDocumentProcessingStatusReturn {
  const { documentId, jobId, enabled = true } = params;
  const { manager, isConnected } = useWebSocket();

  // State for processing information
  const [progress, setProgress] = useState<number>(0);
  const [currentStep, setCurrentStep] = useState<string>('Initializing...');
  const [error, setError] = useState<string | null>(null);
  const [estimatedRemainingSeconds, setEstimatedRemainingSeconds] = useState<number | undefined>();
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [status, setStatus] = useState<Document['processing_status']>('queued');
  const [result, setResult] = useState<any>();

  // Use ref to store latest values for comparison
  const lastUpdateRef = useRef<DocumentProcessingUpdate | null>(null);

  // Handler for processing updates
  const handleProcessingUpdate = useCallback(
    (data: DocumentProcessingUpdate) => {
      // Access payload from WebSocket message
      const payload = data.payload;

      // Filter by document ID or job ID
      const matchesDocument = payload.document_id === documentId;
      const matchesJob = jobId ? payload.job_id === jobId : true;

      if (!matchesDocument || !matchesJob) {
        return; // Not for this document
      }

      // Store reference for debugging
      lastUpdateRef.current = data;

      // Update state from WebSocket payload
      if (payload.progress !== undefined) {
        setProgress(Math.min(100, Math.max(0, payload.progress)));
      }

      if (payload.current_step) {
        setCurrentStep(payload.current_step);
      }

      if (payload.error_message) {
        setError(payload.error_message);
      } else if (payload.status === 'indexed' || payload.status === 'processing') {
        // Clear error when processing resumes or completes successfully
        setError(null);
      }

      if (payload.estimated_remaining_seconds !== undefined) {
        setEstimatedRemainingSeconds(payload.estimated_remaining_seconds);
      }

      if (payload.status) {
        setStatus(payload.status);
      }

      // Update timestamp
      setLastUpdate(new Date());
    },
    [documentId, jobId]
  );

  // Subscribe to WebSocket updates
  useEffect(() => {
    if (!manager || !enabled || !isConnected) {
      return;
    }

    // Subscribe to document processing updates
    manager.on('document_processing_update', handleProcessingUpdate);

    // Cleanup subscription on unmount
    return () => {
      manager.off('document_processing_update', handleProcessingUpdate);
    };
  }, [manager, enabled, isConnected, handleProcessingUpdate]);

  // Reset state when documentId changes
  useEffect(() => {
    setProgress(0);
    setCurrentStep('Initializing...');
    setError(null);
    setEstimatedRemainingSeconds(undefined);
    setLastUpdate(null);
    setStatus('queued');
    setResult(undefined);
    lastUpdateRef.current = null;
  }, [documentId]);

  return {
    progress,
    currentStep,
    error,
    estimatedRemainingSeconds,
    isConnected,
    lastUpdate,
    status,
    result,
  };
}

export default useDocumentProcessingStatus;
