/**
 * Citation Store - Zustand state management for Research Assistant citations
 */

import { create } from 'zustand';
import { citationService } from '@/services/citationService';
import type { CitationResponse } from '@/types/research';

interface CitationState {
  // State
  citations: CitationResponse[];
  citationsByMessage: Record<string, CitationResponse[]>;
  loading: boolean;
  error: string | null;

  // Actions
  fetchCitationsForMessage: (messageId: string) => Promise<void>;
  addCitation: (citation: CitationResponse) => void;
  clearCitations: () => void;
  setError: (error: string | null) => void;
}

export const useCitationStore = create<CitationState>((set, get) => ({
  // Initial state
  citations: [],
  citationsByMessage: {},
  loading: false,
  error: null,

  // Fetch citations for a specific message
  fetchCitationsForMessage: async (messageId: string) => {
    set({ loading: true, error: null });

    try {
      const citations = await citationService.getCitationsForMessage(messageId);
      
      set((state) => ({
        citations: [...state.citations, ...citations],
        citationsByMessage: {
          ...state.citationsByMessage,
          [messageId]: citations,
        },
        loading: false,
      }));
    } catch (error: any) {
      console.error('[CitationStore] Failed to fetch citations:', error);
      set({
        error: error?.message || 'Failed to fetch citations',
        loading: false,
      });
    }
  },

  // Add a single citation to the store
  addCitation: (citation: CitationResponse) => {
    set((state) => {
      const messageId = citation.messageId;

      // Add to global citations array if not already present
      const existingCitations = state.citations.some(c => c.id === citation.id)
        ? state.citations
        : [...state.citations, citation];

      // If no messageId, just update citations without modifying citationsByMessage
      if (!messageId) {
        return { citations: existingCitations };
      }

      // Add to message-specific citations
      const messageCitations = [...(state.citationsByMessage[messageId] || []), citation];

      return {
        citations: existingCitations,
        citationsByMessage: {
          ...state.citationsByMessage,
          [messageId]: messageCitations,
        },
      };
    });
  },

  // Clear all citations
  clearCitations: () => {
    set({
      citations: [],
      citationsByMessage: {},
      error: null,
    });
  },

  // Set error message
  setError: (error: string | null) => {
    set({ error });
  },
}));

export default useCitationStore;
