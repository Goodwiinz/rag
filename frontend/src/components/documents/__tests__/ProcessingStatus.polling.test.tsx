/**
 * ProcessingStatus polling tests.
 *
 * Replaces the WebSocket subscription (R4-H1/H2/H3: handshake/payload-shape
 * mismatch, server emitted no events) with polling of
 * GET /processing/documents/{id}/status. These tests fail if the polling
 * interval or refetch logic is removed or broken.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { ProcessingStatus } from '../ProcessingStatus';
import type { Document } from '@/types';

const mockGet = vi.fn();

vi.mock('@/services/api-client', () => ({
  api: {
    get: (...args: unknown[]) => mockGet(...args),
  },
}));

function makeDocument(overrides: Partial<Document> = {}): Document {
  return {
    id: 'doc-1',
    user_id: 'user-1',
    organization_id: 'org-1',
    title: 'Test Document',
    filename: 'test.pdf',
    file_type: 'pdf',
    processing_status: 'processing',
    upload_timestamp: '2026-01-01T00:00:00Z',
    ...overrides,
  } as Document;
}

beforeEach(() => {
  vi.useFakeTimers();
  mockGet.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('ProcessingStatus polling', () => {
  it('polls GET /processing/documents/{id}/status every 3s while enabled and non-terminal', async () => {
    mockGet.mockResolvedValue({
      document_id: 'doc-1',
      processing_status: 'processing',
      is_embedded: false,
      is_indexed: false,
      processing_error: null,
    });

    render(
      <ProcessingStatus document={makeDocument()} enableRealtime compact />
    );

    // Initial poll fires immediately on mount.
    await act(async () => {
      await Promise.resolve();
    });
    expect(mockGet).toHaveBeenCalledWith(
      '/processing/documents/doc-1/status'
    );
    expect(mockGet).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(3000);
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(mockGet).toHaveBeenCalledTimes(2);

    await act(async () => {
      vi.advanceTimersByTime(3000);
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(mockGet).toHaveBeenCalledTimes(3);
  });

  it('stops polling once the endpoint reports a terminal status', async () => {
    mockGet.mockResolvedValueOnce({
      document_id: 'doc-1',
      processing_status: 'processing',
      is_embedded: false,
      is_indexed: false,
      processing_error: null,
    });
    mockGet.mockResolvedValueOnce({
      document_id: 'doc-1',
      processing_status: 'completed',
      is_embedded: true,
      is_indexed: true,
      processing_error: null,
    });

    render(
      <ProcessingStatus document={makeDocument()} enableRealtime compact />
    );

    await act(async () => {
      await Promise.resolve();
    });
    expect(mockGet).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(3000);
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(mockGet).toHaveBeenCalledTimes(2);

    // No further calls after reaching a terminal status.
    await act(async () => {
      vi.advanceTimersByTime(9000);
      await Promise.resolve();
    });
    expect(mockGet).toHaveBeenCalledTimes(2);
  });

  it('does not poll when enableRealtime is false', async () => {
    mockGet.mockResolvedValue({
      document_id: 'doc-1',
      processing_status: 'processing',
      is_embedded: false,
      is_indexed: false,
      processing_error: null,
    });

    render(<ProcessingStatus document={makeDocument()} compact />);

    await act(async () => {
      vi.advanceTimersByTime(9000);
      await Promise.resolve();
    });
    expect(mockGet).not.toHaveBeenCalled();
  });

  it('does not poll for a document that is already indexed', async () => {
    mockGet.mockResolvedValue({
      document_id: 'doc-1',
      processing_status: 'completed',
      is_embedded: true,
      is_indexed: true,
      processing_error: null,
    });

    render(
      <ProcessingStatus
        document={makeDocument({ processing_status: 'indexed' })}
        enableRealtime
        compact
      />
    );

    await act(async () => {
      vi.advanceTimersByTime(9000);
      await Promise.resolve();
    });
    expect(mockGet).not.toHaveBeenCalled();
    expect(screen.getByText('Processing completed')).toBeInTheDocument();
  });

  it('stops polling on unmount', async () => {
    mockGet.mockResolvedValue({
      document_id: 'doc-1',
      processing_status: 'processing',
      is_embedded: false,
      is_indexed: false,
      processing_error: null,
    });

    const { unmount } = render(
      <ProcessingStatus document={makeDocument()} enableRealtime compact />
    );

    await act(async () => {
      await Promise.resolve();
    });
    expect(mockGet).toHaveBeenCalledTimes(1);

    unmount();

    await act(async () => {
      vi.advanceTimersByTime(9000);
      await Promise.resolve();
    });
    expect(mockGet).toHaveBeenCalledTimes(1);
  });
});
