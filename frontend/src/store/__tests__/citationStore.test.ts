/**
 * Unit tests for Citation Store (Zustand)
 *
 * Tests initial state, adding/clearing citations,
 * fetching citations for messages, and error handling.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mocked } from 'vitest';
import { act } from '@testing-library/react';
import { useCitationStore } from '../citationStore';
import { citationService } from '@/services/citationService';
import type { CitationResponse } from '@/types/research';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('@/services/citationService', () => ({
  citationService: {
    getCitationsForMessage: vi.fn(),
  },
}));

const mockService = citationService as Mocked<typeof citationService>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createMockCitation(
  overrides: Partial<CitationResponse> = {}
): CitationResponse {
  return {
    id: 'cit-1',
    messageId: 'msg-1',
    documentId: 'doc-1',
    documentTitle: 'Test Paper',
    documentType: 'pdf',
    authors: ['Author A'],
    year: 2024,
    venue: 'Test Conference',
    score: 0.95,
    metadataSource: 'rag',
    needsReview: false,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, 'error').mockImplementation();

  // Reset store to initial state between tests
  act(() => {
    useCitationStore.setState({
      citations: [],
      citationsByMessage: {},
      loading: false,
      error: null,
    });
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useCitationStore', () => {
  // =========================================================================
  // Initial State
  // =========================================================================

  describe('initial state', () => {
    it('should have empty initial state', () => {
      const state = useCitationStore.getState();

      expect(state.citations).toEqual([]);
      expect(state.citationsByMessage).toEqual({});
      expect(state.loading).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  // =========================================================================
  // addCitation
  // =========================================================================

  describe('addCitation', () => {
    it('adds a citation to the global citations array', () => {
      const citation = createMockCitation({ id: 'cit-1', messageId: 'msg-1' });

      act(() => {
        useCitationStore.getState().addCitation(citation);
      });

      const state = useCitationStore.getState();
      expect(state.citations).toHaveLength(1);
      expect(state.citations[0].id).toBe('cit-1');
    });

    it('adds the citation to the message-specific index', () => {
      const citation = createMockCitation({ id: 'cit-1', messageId: 'msg-1' });

      act(() => {
        useCitationStore.getState().addCitation(citation);
      });

      const state = useCitationStore.getState();
      expect(state.citationsByMessage['msg-1']).toHaveLength(1);
      expect(state.citationsByMessage['msg-1'][0].id).toBe('cit-1');
    });

    it('does not duplicate citations with the same id in global array', () => {
      const citation = createMockCitation({ id: 'cit-1', messageId: 'msg-1' });

      act(() => {
        useCitationStore.getState().addCitation(citation);
      });

      act(() => {
        useCitationStore.getState().addCitation(citation);
      });

      const state = useCitationStore.getState();
      // Global array should not have duplicates
      expect(state.citations).toHaveLength(1);
    });

    it('adds multiple different citations correctly', () => {
      const citation1 = createMockCitation({ id: 'cit-1', messageId: 'msg-1' });
      const citation2 = createMockCitation({ id: 'cit-2', messageId: 'msg-1' });

      act(() => {
        useCitationStore.getState().addCitation(citation1);
      });

      act(() => {
        useCitationStore.getState().addCitation(citation2);
      });

      const state = useCitationStore.getState();
      expect(state.citations).toHaveLength(2);
      expect(state.citationsByMessage['msg-1']).toHaveLength(2);
    });

    it('groups citations by different message IDs', () => {
      const citationA = createMockCitation({ id: 'cit-1', messageId: 'msg-1' });
      const citationB = createMockCitation({ id: 'cit-2', messageId: 'msg-2' });

      act(() => {
        useCitationStore.getState().addCitation(citationA);
      });

      act(() => {
        useCitationStore.getState().addCitation(citationB);
      });

      const state = useCitationStore.getState();
      expect(state.citations).toHaveLength(2);
      expect(state.citationsByMessage['msg-1']).toHaveLength(1);
      expect(state.citationsByMessage['msg-2']).toHaveLength(1);
    });

    it('handles citation without messageId (only updates global array)', () => {
      const citation = createMockCitation({
        id: 'cit-1',
        messageId: undefined,
      });

      act(() => {
        useCitationStore.getState().addCitation(citation);
      });

      const state = useCitationStore.getState();
      expect(state.citations).toHaveLength(1);
      // citationsByMessage should not be affected
      expect(Object.keys(state.citationsByMessage)).toHaveLength(0);
    });
  });

  // =========================================================================
  // clearCitations
  // =========================================================================

  describe('clearCitations', () => {
    it('removes all citations from global array and message index', () => {
      // Populate store
      act(() => {
        useCitationStore
          .getState()
          .addCitation(createMockCitation({ id: 'cit-1', messageId: 'msg-1' }));
        useCitationStore
          .getState()
          .addCitation(createMockCitation({ id: 'cit-2', messageId: 'msg-2' }));
      });

      // Verify populated
      expect(useCitationStore.getState().citations).toHaveLength(2);

      act(() => {
        useCitationStore.getState().clearCitations();
      });

      const state = useCitationStore.getState();
      expect(state.citations).toEqual([]);
      expect(state.citationsByMessage).toEqual({});
    });

    it('clears any existing error', () => {
      act(() => {
        useCitationStore.getState().setError('Some error');
      });

      expect(useCitationStore.getState().error).toBe('Some error');

      act(() => {
        useCitationStore.getState().clearCitations();
      });

      expect(useCitationStore.getState().error).toBeNull();
    });
  });

  // =========================================================================
  // setError
  // =========================================================================

  describe('setError', () => {
    it('sets an error message', () => {
      act(() => {
        useCitationStore.getState().setError('Something went wrong');
      });

      expect(useCitationStore.getState().error).toBe('Something went wrong');
    });

    it('clears the error when null is passed', () => {
      act(() => {
        useCitationStore.getState().setError('Some error');
      });

      act(() => {
        useCitationStore.getState().setError(null);
      });

      expect(useCitationStore.getState().error).toBeNull();
    });
  });

  // =========================================================================
  // fetchCitationsForMessage
  // =========================================================================

  describe('fetchCitationsForMessage', () => {
    it('sets loading state while fetching', async () => {
      const citations = [createMockCitation({ id: 'cit-1' })];
      mockService.getCitationsForMessage.mockResolvedValue(citations);

      const promise = useCitationStore
        .getState()
        .fetchCitationsForMessage('msg-1');

      // Should be loading during the request
      expect(useCitationStore.getState().loading).toBe(true);

      await promise;

      expect(useCitationStore.getState().loading).toBe(false);
    });

    it('stores fetched citations in both global and per-message indices', async () => {
      const citations = [
        createMockCitation({ id: 'cit-1', messageId: 'msg-1' }),
        createMockCitation({ id: 'cit-2', messageId: 'msg-1' }),
      ];
      mockService.getCitationsForMessage.mockResolvedValue(citations);

      await act(async () => {
        await useCitationStore.getState().fetchCitationsForMessage('msg-1');
      });

      const state = useCitationStore.getState();
      expect(state.citations).toHaveLength(2);
      expect(state.citationsByMessage['msg-1']).toHaveLength(2);
      expect(state.error).toBeNull();
    });

    it('calls citationService.getCitationsForMessage with the correct messageId', async () => {
      mockService.getCitationsForMessage.mockResolvedValue([]);

      await act(async () => {
        await useCitationStore.getState().fetchCitationsForMessage('msg-42');
      });

      expect(mockService.getCitationsForMessage).toHaveBeenCalledWith('msg-42');
    });

    it('appends new citations to existing citations', async () => {
      // Pre-populate store with an existing citation
      act(() => {
        useCitationStore
          .getState()
          .addCitation(
            createMockCitation({ id: 'existing', messageId: 'msg-0' })
          );
      });

      const newCitations = [
        createMockCitation({ id: 'new-1', messageId: 'msg-1' }),
      ];
      mockService.getCitationsForMessage.mockResolvedValue(newCitations);

      await act(async () => {
        await useCitationStore.getState().fetchCitationsForMessage('msg-1');
      });

      const state = useCitationStore.getState();
      expect(state.citations).toHaveLength(2); // existing + new
    });

    it('sets error state on service failure', async () => {
      mockService.getCitationsForMessage.mockRejectedValue(
        new Error('API unavailable')
      );

      await act(async () => {
        await useCitationStore.getState().fetchCitationsForMessage('msg-1');
      });

      const state = useCitationStore.getState();
      expect(state.error).toBe('API unavailable');
      expect(state.loading).toBe(false);
    });

    it('handles non-Error rejections gracefully', async () => {
      mockService.getCitationsForMessage.mockRejectedValue('string error');

      await act(async () => {
        await useCitationStore.getState().fetchCitationsForMessage('msg-1');
      });

      const state = useCitationStore.getState();
      expect(state.error).toBe('Failed to fetch citations');
      expect(state.loading).toBe(false);
    });

    it('clears previous error before starting fetch', async () => {
      // Set an initial error
      act(() => {
        useCitationStore.getState().setError('Old error');
      });

      mockService.getCitationsForMessage.mockResolvedValue([]);

      await act(async () => {
        await useCitationStore.getState().fetchCitationsForMessage('msg-1');
      });

      expect(useCitationStore.getState().error).toBeNull();
    });
  });
});
