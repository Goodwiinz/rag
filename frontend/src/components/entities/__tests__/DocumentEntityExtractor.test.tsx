import { Mock, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { DocumentEntityExtractor } from '@/components/entities/DocumentEntityExtractor';
import toast from 'react-hot-toast';
import { apiClient } from '@/services/apiClient';

class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

(global as typeof global & { ResizeObserver?: typeof MockResizeObserver }).ResizeObserver =
  MockResizeObserver;

vi.mock('react-hot-toast', () => ({
  __esModule: true,
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock('@/services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

describe('DocumentEntityExtractor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('handles documents fetch failure without logging console.error', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    (apiClient.get as Mock).mockRejectedValue(new Error('Request failed'));

    render(<DocumentEntityExtractor />);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to fetch documents');
    });

    expect(consoleErrorSpy).not.toHaveBeenCalled();
    consoleErrorSpy.mockRestore();
  });
});
