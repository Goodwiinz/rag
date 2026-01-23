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

  /**
   * Extract citation metadata using hybrid extraction pipeline
   * @param documentId - Document ID to extract from
   * @param strategy - Extraction strategy (auto/arxiv/semantic_scholar/crossref)
   */
  async extractCitations(
    documentId?: string,
    strategy: string = 'auto'
  ): Promise<CitationResponse> {
    const response = await apiClient.post<CitationResponse>('/citations/extract', {
      document_id: documentId,
      strategy,
    });
    return response.data;
  },

  /**
   * Lookup citation by ArXiv ID, DOI, or title
   * Returns citation metadata without persisting to database
   */
  async lookupCitation(params: {
    arxivId?: string;
    doi?: string;
    title?: string;
  }): Promise<CitationResponse> {
    const response = await apiClient.post<CitationResponse>('/citations/lookup', {
      arxiv_id: params.arxivId,
      doi: params.doi,
      title: params.title,
    });
    return response.data;
  },

  /**
   * Export bibliography in specified format
   * @param format - Bibliography format (bibtex/ieee/apa/mla)
   * @param citationIds - Optional list of citation IDs to export
   * @param projectId - Optional project ID to export all citations from
   * @returns Formatted bibliography as text
   */
  async exportBibliography(
    format: 'bibtex' | 'ieee' | 'apa' | 'mla',
    citationIds?: string[],
    projectId?: string
  ): Promise<string> {
    const response = await apiClient.post<string>(
      '/citations/export',
      {
        format,
        citation_ids: citationIds,
        project_id: projectId,
      },
      {
        responseType: 'text',
      }
    );
    return response.data;
  },

  /**
   * Download bibliography as a file
   * @param format - Bibliography format
   * @param citationIds - Optional list of citation IDs
   * @param projectId - Optional project ID
   * @param filename - Optional custom filename
   */
  async downloadBibliography(
    format: 'bibtex' | 'ieee' | 'apa' | 'mla',
    citationIds?: string[],
    projectId?: string,
    filename?: string
  ): Promise<void> {
    const bibliography = await this.exportBibliography(format, citationIds, projectId);

    // Create blob and download
    const blob = new Blob([bibliography], {
      type: format === 'bibtex' ? 'application/x-bibtex' : 'text/plain',
    });

    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename || `bibliography.${format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },

  // =========================================================================
  // Citation Graph Methods (T058)
  // =========================================================================

  /**
   * Get citation graph data for visualization
   * @param projectId - Optional project filter
   * @param documentId - Optional document filter
   * @param depth - Graph traversal depth (1-5)
   * @param includeExternal - Include external papers
   */
  async getCitationGraph(params?: {
    projectId?: string;
    documentId?: string;
    depth?: number;
    includeExternal?: boolean;
  }): Promise<GraphData> {
    const response = await apiClient.get<GraphData>('/citations/graph', {
      params: {
        project_id: params?.projectId,
        document_id: params?.documentId,
        depth: params?.depth || 2,
        include_external: params?.includeExternal ?? true,
      },
    });
    return response.data;
  },

  /**
   * Get detailed information about a specific graph node
   * @param citationId - Citation ID to get details for
   */
  async getGraphNodeDetails(citationId: string): Promise<GraphNodeDetails> {
    const response = await apiClient.get<GraphNodeDetails>(
      `/citations/graph/node/${citationId}`
    );
    return response.data;
  },

  /**
   * List citation relationships
   * @param sourceId - Optional source citation filter
   * @param targetId - Optional target citation filter
   */
  async listRelationships(params?: {
    sourceId?: string;
    targetId?: string;
    relationshipType?: string;
  }): Promise<RelationshipsResponse> {
    const response = await apiClient.get<RelationshipsResponse>(
      '/citations/relationships',
      {
        params: {
          source_id: params?.sourceId,
          target_id: params?.targetId,
          relationship_type: params?.relationshipType,
        },
      }
    );
    return response.data;
  },

  /**
   * Create a citation relationship
   * @param sourceCitationId - The citing paper
   * @param targetCitationId - The cited paper
   * @param relationshipType - Type of relationship
   * @param citationContext - Optional text context
   * @param confidence - Confidence score
   */
  async createRelationship(params: {
    sourceCitationId: string;
    targetCitationId: string;
    relationshipType?: string;
    citationContext?: string;
    confidence?: number;
  }): Promise<RelationshipResponse> {
    const response = await apiClient.post<RelationshipResponse>(
      '/citations/relationships',
      null,
      {
        params: {
          source_citation_id: params.sourceCitationId,
          target_citation_id: params.targetCitationId,
          relationship_type: params.relationshipType || 'CITES',
          citation_context: params.citationContext,
          confidence: params.confidence || 1.0,
        },
      }
    );
    return response.data;
  },
};

// Graph-related types
export interface GraphNode {
  id: string;
  title?: string;
  authors?: string[];
  year?: number;
  venue?: string;
  doi?: string;
  arxiv_id?: string;
  document_id?: string;
  is_uploaded?: boolean;
  citation_count?: number;
  position?: { x: number; y: number } | null;
  influence_score?: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type?: string;
  confidence?: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata?: {
    total_nodes: number;
    total_edges: number;
    depth: number;
    include_external: boolean;
  };
}

export interface GraphNodeDetails {
  id: string;
  document_id?: string;
  title?: string;
  authors?: string[];
  year?: number;
  venue?: string;
  doi?: string;
  arxiv_id?: string;
  is_uploaded?: boolean;
  cited_by: number;
  cites: number;
  influence_score: number;
}

export interface RelationshipResponse {
  id: string;
  source_citation_id: string;
  target_citation_id: string;
  relationship_type: string;
  citation_context?: string;
  confidence: number;
  created_at?: string;
}

export interface RelationshipsResponse {
  relationships: RelationshipResponse[];
  total: number;
}

export default citationService;
