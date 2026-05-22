/**
 * Entity Service - API Client for Entity Operations
 *
 * Handles entity CRUD operations, relationship management,
 * and entity-specific data consumption from backend.
 */

import { Entity, EntityResponse, EntityType, GraphEdge } from '@/types/entity';
import { EntityDetails, GraphNode } from '@/types/graph-api';
import { api } from '@/services/api-client';
import { APIErrorClass } from '@/types/api';

/**
 * Retry wrapper utility for API calls
 * Automatically retries failed requests once with exponential backoff
 */
async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number = 1
): Promise<T> {
  let lastError: Error | undefined;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      if (attempt < maxRetries) {
        // Exponential backoff: wait 1s on first retry, 2s on second, etc.
        await new Promise((r) => setTimeout(r, 1000 * (attempt + 1)));
      }
    }
  }

  throw lastError;
}

const isExpectedApiFailure = (error: unknown): boolean => {
  if (error instanceof APIErrorClass) {
    const message = error.error.message?.toLowerCase() || '';
    return (
      !!error.error.silent ||
      error.error.status_code === 401 ||
      error.error.status_code === 403 ||
      error.error.status_code === 503 ||
      message.includes('service unavailable') ||
      message.includes('circuit breaker')
    );
  }
  return false;
};

const logEntityServiceError = (context: string, error: unknown): void => {
  if (isExpectedApiFailure(error)) {
    console.warn(`${context}:`, error);
    return;
  }
  console.error(`${context}:`, error);
};

export interface EntityUpdateRequest {
  name?: string;
  confidence_score?: number;
  metadata?: Record<string, any>;
}

export interface PaginatedEntitiesResponse {
  entities: EntityResponse[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface RelationshipUpdateRequest {
  type?: string;
  weight?: number;
  confidence?: number;
  metadata?: Record<string, any>;
}

export interface EntityTimeline {
  entityId: string;
  events: Array<{
    timestamp: string;
    type: 'created' | 'updated' | 'relationship_added' | 'relationship_removed';
    description: string;
    metadata?: Record<string, any>;
  }>;
}

export interface ProcessingJobStatus {
  id: string;
  job_type: string;
  status: string;
  progress_percentage: number;
  current_step?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  error_message?: string;
  result?: Record<string, any>;
}

export interface ProcessingJobsListResponse {
  jobs: ProcessingJobStatus[];
  total: number;
  limit: number;
  offset: number;
}

class EntityService {
  private baseUrl = '/knowledge-graph';

  /**
   * Get all entities with pagination (with retry)
   */
  async getEntities(
    limit: number = 100,
    offset: number = 0,
    entityTypes?: EntityType[],
    connectedOnly?: boolean
  ): Promise<PaginatedEntitiesResponse> {
    return withRetry(async () => {
      const params: Record<string, any> = { limit, offset };
      if (entityTypes && entityTypes.length > 0) {
        params.entity_types = entityTypes;
      }
      if (connectedOnly) {
        params.connected_only = true;
      }
      const qs = new URLSearchParams(
        Object.entries(params).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])
      ).toString();
      const response = await api.get(`${this.baseUrl}/entities${qs ? `?${qs}` : ''}`);
      return response as PaginatedEntitiesResponse;
    });
  }

  /**
   * Get all relationships
   */
  async getAllRelationships(
    limit: number = 200,
    offset: number = 0
  ): Promise<GraphEdge[]> {
    try {
      const response = await api.get(`${this.baseUrl}/relationships?limit=${limit}&offset=${offset}`);
      // Transform backend response to GraphEdge format
      const relationships = (response as any[]) || [];
      return relationships.map((rel) => ({
        id: rel.id,
        source: rel.source_entity_id,
        target: rel.target_entity_id,
        type: rel.relationship_type,
        weight: rel.strength,
        strength: rel.strength,
        confidence: rel.confidence_score,
        context: rel.context,
        metadata: rel.metadata,
      }));
    } catch (error) {
      logEntityServiceError('Error in getAllRelationships', error);
      return [];
    }
  }

  /**
   * Get entity by ID - backend retrieves with all metadata
   */
  async getEntity(entityId: string): Promise<Entity> {
    const response = await api.get<Entity>(
      `${this.baseUrl}/entities/${entityId}`
    );
    return response;
  }

  /**
   * Create new entity (with retry)
   */
  async createEntity(entityData: Partial<Entity>): Promise<Entity> {
    return withRetry(async () => {
      const response = await api.post<Entity>(
        `${this.baseUrl}/entities`,
        entityData
      );
      return response;
    });
  }

  /**
   * Update entity - backend validates and persists changes
   */
  async updateEntity(
    entityId: string,
    updates: EntityUpdateRequest
  ): Promise<Entity> {
    const response = await api.put<Entity>(
      `${this.baseUrl}/entities/${entityId}`,
      updates
    );
    return response;
  }

  /**
   * Delete entity - backend handles cascading deletions
   */
  async deleteEntity(entityId: string): Promise<void> {
    await api.delete(`${this.baseUrl}/entities/${entityId}`);
  }

  /**
   * Search entities
   */
  async searchEntities(
    query: string,
    entityTypes?: string[],
    limit: number = 50
  ): Promise<Entity[]> {
    const qs = new URLSearchParams(
      Object.entries({ query, entity_types: entityTypes?.join(','), limit: String(limit) })
        .filter(([, v]) => v !== undefined) as [string, string][]
    ).toString();
    const response = await api.get<Entity[]>(
      `${this.baseUrl}/entities/search${qs ? `?${qs}` : ''}`
    );
    return response;
  }

  /**
   * Get entity relationships - backend computes relationship strength
   */
  async getEntityRelationships(
    entityId: string,
    relationshipType?: string,
    limit: number = 50
  ): Promise<GraphEdge[]> {
    const qs = new URLSearchParams(
      Object.entries({ relationship_type: relationshipType, limit: String(limit) })
        .filter(([, v]) => v !== undefined && v !== 'undefined') as [string, string][]
    ).toString();
    const response = await api.get<GraphEdge[]>(
      `${this.baseUrl}/entities/${entityId}/relationships${qs ? `?${qs}` : ''}`
    );
    return response;
  }

  /**
   * Create relationship between entities (with retry)
   */
  async createRelationship(relationshipData: {
    source_entity_id: string;
    target_entity_id: string;
    relationship_type: string;
    strength?: number;
    confidence_score?: number;
    context?: string;
    evidence?: string[];
    metadata?: Record<string, any>;
  }): Promise<GraphEdge> {
    return withRetry(async () => {
      const response = await api.post<GraphEdge>(
        `${this.baseUrl}/relationships`,
        relationshipData
      );
      return response;
    });
  }

  /**
   * Delete relationship
   */
  async deleteRelationship(relationshipId: string): Promise<void> {
    await api.delete(`${this.baseUrl}/relationships/${relationshipId}`);
  }

  /**
   * Get entity details with extended metadata, relationships, and documents
   */
  async getEntityDetails(entityId: string): Promise<EntityDetails> {
    const response = await api.get<EntityDetails>(
      `${this.baseUrl}/entities/${entityId}/details`
    );
    return response;
  }

  async createMergeJob(
    groups: Array<{
      entities: Array<{ id: string; name: string }>;
      suggested_primary: string;
    }>
  ): Promise<{ job_id: string; status: string }> {
    return api.post<{ job_id: string; status: string }>(
      `${this.baseUrl}/merge-jobs`,
      { groups }
    );
  }

  async createExtractionJob(
    documentIds: string[]
  ): Promise<{ job_id: string; status: string }> {
    return api.post<{ job_id: string; status: string }>(
      `${this.baseUrl}/extraction-jobs`,
      { document_ids: documentIds }
    );
  }

  async getProcessingJob(jobId: string): Promise<ProcessingJobStatus> {
    return api.get<ProcessingJobStatus>(`/processing/jobs/${jobId}`);
  }

  async listProcessingJobs(params?: {
    status?: string;
    job_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<ProcessingJobsListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.append('status', params.status);
    if (params?.job_type) searchParams.append('job_type', params.job_type);
    if (params?.limit !== undefined) searchParams.append('limit', params.limit.toString());
    if (params?.offset !== undefined) searchParams.append('offset', params.offset.toString());
    const qs = searchParams.toString();
    return api.get<ProcessingJobsListResponse>(`/processing/jobs${qs ? `?${qs}` : ''}`);
  }

  /**
   * Find similar entities based on embedding similarity
   */
  async findSimilarEntities(
    entityId: string,
    limit: number = 10,
    minSimilarity: number = 0.5
  ): Promise<Array<{ entity: GraphNode; similarity: number }>> {
    const response = await api.get<
      Array<{ entity: GraphNode; similarity: number }>
    >(`${this.baseUrl}/entities/${entityId}/similar?limit=${limit}&min_similarity=${minSimilarity}`);
    return response;
  }

  /**
   * Get entity timeline events
   */
  async getEntityTimeline(entityId: string): Promise<EntityTimeline> {
    const response = await api.get<EntityTimeline>(
      `${this.baseUrl}/entities/${entityId}/timeline`
    );
    return response;
  }

  /**
   * Get all available entity types from the backend (with retry)
   */
  async getEntityTypes(): Promise<string[]> {
    try {
      return await withRetry(async () => {
        const response = await api.get<string[]>(
          `${this.baseUrl}/entity-types`
        );
        return response;
      });
    } catch (error) {
      logEntityServiceError('Error fetching entity types', error);
      // Return fallback hardcoded types if API fails after retry
      return [
        'PERSON',
        'ORGANIZATION',
        'LOCATION',
        'CONCEPT',
        'EVENT',
        'PRODUCT',
        'DATE',
        'TECHNOLOGY',
        'DOCUMENT',
        'OTHER',
      ];
    }
  }

  /**
   * Get all available relationship types from the backend
   */
  async getRelationshipTypes(): Promise<string[]> {
    try {
      const response = await api.get<string[]>(
        `${this.baseUrl}/relationship-types`
      );
      return response;
    } catch (error) {
      logEntityServiceError('Error fetching relationship types', error);
      // Return fallback types matching backend RelationshipType enum
      return [
        'WORKS_FOR',
        'KNOWS',
        'RELATED_TO',
        'LOCATED_IN',
        'PART_OF',
        'MENTIONED_IN',
        'APPEARS_WITH',
        'CREATED_BY',
        'OWNS',
        'MANAGES',
        'COLLABORATES_WITH',
        'REPORTS_TO',
        'MEMBER_OF',
        'ATTENDED',
        'SPOKE_AT',
        'PUBLISHED_BY',
        'CITED',
        'REFERENCES',
        'CUSTOM',
      ];
    }
  }

  /**
   * Get server-side visualization data for an entity's neighborhood
   */
  async getVisualizationData(
    entityId: string,
    depth: number = 2,
    maxNodes: number = 50
  ): Promise<any> {
    try {
      const response = await api.get(
        `${this.baseUrl}/visualization/${entityId}?depth=${depth}&max_nodes=${maxNodes}`
      );
      return response;
    } catch (error) {
      logEntityServiceError('Error fetching visualization data', error);
      throw error;
    }
  }

  /**
   * Perform comprehensive graph search with paths
   */
  async searchGraph(params: {
    query: string;
    entity_types?: string[];
    relationship_types?: string[];
    max_depth?: number;
    min_strength?: number;
    max_results?: number;
  }): Promise<any> {
    try {
      const response = await api.post(`${this.baseUrl}/search`, params);
      return response;
    } catch (error) {
      logEntityServiceError('Error performing graph search', error);
      throw error;
    }
  }

  /**
   * Batch create entities and relationships
   */
  async batchCreate(params: {
    entities: Partial<Entity>[];
    relationships?: any[];
    upsert?: boolean;
  }): Promise<any> {
    try {
      const response = await api.post(`${this.baseUrl}/batch`, params);
      return response;
    } catch (error) {
      logEntityServiceError('Error in batch create', error);
      throw error;
    }
  }

  /**
   * Get related entities in neighborhood (with retry)
   */
  async getRelatedEntities(
    entityId: string,
    maxDepth: number = 2,
    minStrength: number = 0.1,
    limit: number = 50
  ): Promise<Entity[]> {
    return withRetry(async () => {
      const response = await api.get(
        `${this.baseUrl}/entities/${entityId}/related?max_depth=${maxDepth}&min_strength=${minStrength}&limit=${limit}`
      );
      return response as Entity[];
    });
  }

  /**
   * Get neighborhood entities and relationships in a single call (with retry)
   */
  async getNeighborhood(
    entityId: string,
    maxDepth: number = 2,
    minStrength: number = 0.1,
    limit: number = 50
  ): Promise<{ entities: Entity[]; relationships: any[] }> {
    return withRetry(async () => {
      const response = await api.get(
        `${this.baseUrl}/entities/${entityId}/neighborhood?max_depth=${maxDepth}&min_strength=${minStrength}&limit=${limit}`
      );
      return response as { entities: Entity[]; relationships: any[] };
    });
  }

  /**
   * Find paths between two entities (with retry)
   */
  async findPaths(
    sourceId: string,
    targetId: string,
    maxDepth: number = 3,
    minStrength: number = 0.1
  ): Promise<any[]> {
    return withRetry(async () => {
      const response = await api.get(
        `${this.baseUrl}/paths/${sourceId}/${targetId}?max_depth=${maxDepth}&min_strength=${minStrength}`
      );
      return response as any[];
    });
  }

  /**
   * Get graph analytics including entity type distribution (with retry)
   */
  async getAnalytics(): Promise<{
    total_entities: number;
    total_relationships: number;
    entity_type_counts: Record<string, number>;
    relationship_type_counts: Record<string, number>;
    orphan_entities: number;
    average_connections: number;
  }> {
    return withRetry(async () => {
      const response = await api.get(`${this.baseUrl}/analytics`);
      return response as any;
    });
  }
}

export const entityService = new EntityService();
