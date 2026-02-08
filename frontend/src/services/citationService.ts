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

const normalizeCitation = (citation: CitationResponse): CitationResponse => {
  const raw = citation as CitationResponse & {
    message_id?: string;
    document_id?: string;
    external_reference_id?: string;
    document_title?: string;
    document_type?: string;
    arxiv_id?: string;
    page_number?: number;
    metadata_source?: string;
    needs_review?: boolean;
    created_at?: string;
    updated_at?: string;
  };

  const normalized: CitationResponse = { ...citation };

  if (!citation.messageId && raw.message_id) normalized.messageId = raw.message_id;
  if (!citation.documentId && raw.document_id) normalized.documentId = raw.document_id;
  if (!citation.externalReferenceId && raw.external_reference_id) {
    normalized.externalReferenceId = raw.external_reference_id;
  }
  if (!citation.documentTitle && raw.document_title) normalized.documentTitle = raw.document_title;
  if (!citation.documentType && raw.document_type) normalized.documentType = raw.document_type;
  if (!citation.arxivId && raw.arxiv_id) normalized.arxivId = raw.arxiv_id;
  if (citation.pageNumber === undefined && raw.page_number !== undefined) {
    normalized.pageNumber = raw.page_number;
  }
  if (!citation.metadataSource && raw.metadata_source) {
    normalized.metadataSource = raw.metadata_source;
  }
  if (citation.needsReview === undefined && raw.needs_review !== undefined) {
    normalized.needsReview = raw.needs_review;
  }
  if (!citation.createdAt && raw.created_at) normalized.createdAt = raw.created_at;
  if (!citation.updatedAt && raw.updated_at) normalized.updatedAt = raw.updated_at;

  return normalized;
};

const normalizeCitationList = (citations: CitationResponse[]): CitationResponse[] =>
  citations.map(normalizeCitation);

export const citationService = {
  /**
   * Create a new citation from chat message context
   */
  async createCitation(data: CitationCreate): Promise<CitationResponse> {
    // Transform camelCase to snake_case for backend API
    const apiData: Record<string, any> = {};
    if (data.messageId) apiData.message_id = data.messageId;
    if (data.documentId) apiData.document_id = data.documentId;
    if (data.externalReferenceId) apiData.external_reference_id = data.externalReferenceId;
    if (data.documentTitle) apiData.document_title = data.documentTitle;
    if (data.documentType) apiData.document_type = data.documentType;
    if (data.authors) apiData.authors = data.authors;
    if (data.year) apiData.year = data.year;
    if (data.venue) apiData.venue = data.venue;
    if (data.doi) apiData.doi = data.doi;
    if (data.arxivId) apiData.arxiv_id = data.arxivId;
    if (data.abstract) apiData.abstract = data.abstract;
    if (data.snippet) apiData.snippet = data.snippet;
    if (data.pageNumber) apiData.page_number = data.pageNumber;
    if (data.score !== undefined) apiData.score = data.score;
    if (data.metadataSource) apiData.metadata_source = data.metadataSource;
    if (data.needsReview !== undefined) apiData.needs_review = data.needsReview;

    const response = await apiClient.post<CitationResponse>('/citations', apiData);
    return normalizeCitation(response);
  },

  /**
   * Get a single citation by ID
   */
  async getCitation(citationId: string): Promise<CitationResponse> {
    const response = await apiClient.get<CitationResponse>(`/citations/${citationId}`);
    return normalizeCitation(response);
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
    // Transform camelCase params to snake_case for backend API
    const apiParams: Record<string, any> = {};
    if (params?.messageId) apiParams.message_id = params.messageId;
    if (params?.documentId) apiParams.document_id = params.documentId;
    if (params?.arxivId) apiParams.arxiv_id = params.arxivId;
    if (params?.doi) apiParams.doi = params.doi;
    if (params?.needsReview !== undefined) apiParams.needs_review = params.needsReview;
    if (params?.skip !== undefined) apiParams.skip = params.skip;
    if (params?.limit !== undefined) apiParams.limit = params.limit;

    const response = await apiClient.get<CitationListResponse>('/citations', {
      params: apiParams,
    });
    return {
      ...response,
      citations: normalizeCitationList(response.citations),
    };
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
    return normalizeCitation(response);
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
    // Backend expects query parameters, not body
    const queryParams: Record<string, string> = {};
    if (params.arxivId) queryParams.arxiv_id = params.arxivId;
    if (params.doi) queryParams.doi = params.doi;
    if (params.title) queryParams.title = params.title;

    const response = await apiClient.post<CitationResponse>('/citations/lookup', null, {
      params: queryParams,
    });
    return normalizeCitation(response);
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
    return apiClient.post<string>(
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
    return apiClient.get<GraphData>('/citations/graph', {
      params: {
        project_id: params?.projectId,
        document_id: params?.documentId,
        depth: params?.depth || 2,
        include_external: params?.includeExternal ?? true,
      },
    });
  },

  /**
   * Get detailed information about a specific graph node
   * @param citationId - Citation ID to get details for
   */
  async getGraphNodeDetails(citationId: string): Promise<GraphNodeDetails> {
    return apiClient.get<GraphNodeDetails>(
      `/citations/graph/node/${citationId}`
    );
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
    return apiClient.get<RelationshipsResponse>(
      '/citations/relationships',
      {
        params: {
          source_id: params?.sourceId,
          target_id: params?.targetId,
          relationship_type: params?.relationshipType,
        },
      }
    );
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
    return apiClient.post<RelationshipResponse>(
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
