/**
 * R4-M16 regression: the poll budget was a fixed 60 attempts x 2s = 2 minutes,
 * but estimateProcessingTime() predicts well over 2 minutes for large video
 * files — the poll gives up long before processing could plausibly finish.
 * maxAttemptsFor() sizes the budget off the estimate, floored at the 5-minute
 * UPLOAD_PROCESSING_TIMEOUT_MS threshold.
 */
import { describe, expect, it } from 'vitest';
import { EnhancedDocumentService } from '@/services/enhancedDocumentService';
import { PERFORMANCE_THRESHOLDS } from '@/types/constants';

type ServiceWithPrivateMaxAttempts = {
  maxAttemptsFor(file: File): number;
};

describe('EnhancedDocumentService.maxAttemptsFor', () => {
  it('floors small files at the 5-minute budget', () => {
    const service =
      new EnhancedDocumentService() as unknown as ServiceWithPrivateMaxAttempts;
    const tinyFile = new File(['hi'], 'note.txt', { type: 'text/plain' });

    expect(service.maxAttemptsFor(tinyFile)).toBe(
      PERFORMANCE_THRESHOLDS.UPLOAD_PROCESSING_TIMEOUT_MS / 2000
    );
  });

  it('sizes the budget above 60 attempts for a large video file', () => {
    const service =
      new EnhancedDocumentService() as unknown as ServiceWithPrivateMaxAttempts;
    const bigVideo = new File([new Uint8Array(100 * 1024 * 1024)], 'movie.mp4', {
      type: 'video/mp4',
    });

    expect(service.maxAttemptsFor(bigVideo)).toBeGreaterThan(60);
  });
});
