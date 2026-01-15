/**
 * Citation Service
 * API client for Research Assistant citation endpoints
 */

import { apiClient } from './apiClient';
import type {
  CitationCreate,
  CitationResponse,
  CitationListResponse,
} from '@/types/research';

export const citationService = {
  /**
   * Create a new citation from chat message context
   */
  async createCitation(data: CitationCreate): Promise<CitationResponse> {
    const response = await apiClient.post<CitationResponse>('/citations', data);
    return response.data;
  },

  /**
   * Get a single citation by ID
   */
  async getCitation(citationId: string): Promise<CitationResponse> {
    const response = await apiClient.get<CitationResponse>(`/citations/${citationId}`);
    return response.data;
  },

  /**
   * List citations with optional filters
   */
  async listCitations(params?: {
    messageId?: string;
    documentId?: string;
    arxivId?: string;
    doi?: string;
    needsReview?: boolean;
    skip?: number;
    limit?: number;
  }): Promise<CitationListResponse> {
    const response = await apiClient.get<CitationListResponse>('/citations', {
      params,
    });
    return response.data;
  },

  /**
   * Fetch citations for a specific message
   */
  async getCitationsForMessage(messageId: string): Promise<CitationResponse[]> {
    const response = await this.listCitations({ messageId });
    return response.citations;
  },

  /**
   * Fetch citations for a specific document
   */
  async getCitationsForDocument(documentId: string): Promise<CitationResponse[]> {
    const response = await this.listCitations({ documentId });
    return response.citations;
  },

  /**
   * Get citations that need review (incomplete metadata)
   */
  async getCitationsNeedingReview(): Promise<CitationResponse[]> {
    const response = await this.listCitations({ needsReview: true });
    return response.citations;
  },
};

export default citationService;
