import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { EntityMergeTool } from '@/components/entities/EntityMergeTool';
import { entityService } from '@/services/entityService';
import { APIErrorClass } from '@/types/api';

class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

(global as typeof global & { ResizeObserver?: typeof MockResizeObserver }).ResizeObserver =
  MockResizeObserver;

jest.mock('@/hooks/useEntityPermissions', () => ({
  useEntityPermissions: () => ({
    canCreate: true,
    canEdit: true,
    canDelete: true,
    canBulkEdit: true,
    isAdmin: true,
  }),
}));

jest.mock('@/services/entityService', () => ({
  entityService: {
    getEntities: jest.fn(),
    createMergeJob: jest.fn(),
    getProcessingJob: jest.fn(),
  },
}));

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

describe('EntityMergeTool', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (entityService.createMergeJob as jest.Mock).mockResolvedValue({
      job_id: 'job-1',
      status: 'queued',
    });
    (entityService.getProcessingJob as jest.Mock).mockResolvedValue({
      id: 'job-1',
      status: 'queued',
      progress_percentage: 10,
      current_step: 'Queued',
    });
  });

  it('selects only filtered duplicate groups when using select all', async () => {
    (entityService.getEntities as jest.Mock).mockResolvedValue({
      entities: [
        {
          id: 'e1',
          name: 'OpenAI',
          entity_type: 'ORGANIZATION',
          confidence_score: 0.9,
          extraction_method: 'ner',
          metadata: {},
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
        {
          id: 'e2',
          name: 'openai',
          entity_type: 'ORGANIZATION',
          confidence_score: 0.8,
          extraction_method: 'ner',
          metadata: {},
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
        {
          id: 'e3',
          name: 'Google',
          entity_type: 'ORGANIZATION',
          confidence_score: 0.95,
          extraction_method: 'ner',
          metadata: {},
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
        {
          id: 'e4',
          name: 'google',
          entity_type: 'ORGANIZATION',
          confidence_score: 0.85,
          extraction_method: 'ner',
          metadata: {},
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 4,
      limit: 100,
      offset: 0,
      has_more: false,
    });

    render(<EntityMergeTool />);

    fireEvent.click(screen.getByRole('button', { name: /find_duplicates/i }));

    await screen.findByText(/Found 2 Duplicate Groups/i);

    fireEvent.change(screen.getByPlaceholderText(/search duplicate groups/i), {
      target: { value: 'openai' },
    });

    fireEvent.click(screen.getByRole('button', { name: /select_all/i }));

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /merge_selected \(1\)/i })
      ).toBeInTheDocument();
    });
  });

  it('shows only one confirmation dialog for batch merge', async () => {
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);
    (entityService.getEntities as jest.Mock).mockResolvedValue({
      entities: [
        {
          id: 'e1',
          name: 'OpenAI',
          entity_type: 'ORGANIZATION',
          confidence_score: 0.9,
          extraction_method: 'ner',
          metadata: {},
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
        {
          id: 'e2',
          name: 'openai',
          entity_type: 'ORGANIZATION',
          confidence_score: 0.8,
          extraction_method: 'ner',
          metadata: {},
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 2,
      limit: 100,
      offset: 0,
      has_more: false,
    });
    render(<EntityMergeTool />);

    fireEvent.click(screen.getByRole('button', { name: /find_duplicates/i }));
    await screen.findByText(/Found 1 Duplicate Group/i);

    fireEvent.click(screen.getByRole('button', { name: /select_all/i }));
    fireEvent.click(screen.getByRole('button', { name: /merge_selected/i }));

    await waitFor(() => {
      expect(confirmSpy).toHaveBeenCalledTimes(1);
    });
    expect(entityService.createMergeJob).toHaveBeenCalledTimes(1);

    confirmSpy.mockRestore();
  });

  it('handles circuit-breaker API errors without console.error spam', async () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    (entityService.getEntities as jest.Mock).mockRejectedValue(
      new APIErrorClass({
        message: 'Neo4j circuit breaker is open - service unavailable',
        status_code: 503,
        type: 'http_error',
        details: {},
      })
    );

    render(<EntityMergeTool />);
    fireEvent.click(screen.getByRole('button', { name: /find_duplicates/i }));

    await screen.findByText(/Knowledge graph is temporarily unavailable/i);
    expect(consoleErrorSpy).not.toHaveBeenCalledWith(
      'Error finding duplicates:',
      expect.anything()
    );
    expect(consoleWarnSpy).toHaveBeenCalled();

    consoleErrorSpy.mockRestore();
    consoleWarnSpy.mockRestore();
  });
});
