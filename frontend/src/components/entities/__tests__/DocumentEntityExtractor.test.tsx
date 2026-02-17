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

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

jest.mock('@/services/apiClient', () => ({
  apiClient: {
    get: jest.fn(),
  },
}));

describe('DocumentEntityExtractor', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('handles documents fetch failure without logging console.error', async () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    (apiClient.get as jest.Mock).mockRejectedValue(new Error('Request failed'));

    render(<DocumentEntityExtractor />);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to fetch documents');
    });

    expect(consoleErrorSpy).not.toHaveBeenCalled();
    consoleErrorSpy.mockRestore();
  });
});
