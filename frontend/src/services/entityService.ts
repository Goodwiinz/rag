/**
 * Entity Service - API Client for Entity Operations
 *
 * Handles entity CRUD operations, relationship management,
 * and entity-specific data consumption from backend.
 */

import { apiClient } from './apiClient';
import { GraphNode, GraphEdge } from './graphService';

export interface EntityUpdateRequest {
  label?: string;
  type?: string;
  metadata?: Record<string, any>;
  confidence?: number;
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

export interface EntityComparison {
  entity1: GraphNode;
  entity2: GraphNode;
  similarities: {
    jaccard: number;
    cosine: number;
    shared_neighbors: string[];
  };
  differences: {
    unique_properties1: Record<string, any>;
    unique_properties2: Record<string, any>;
    unique_neighbors1: string[];
    unique_neighbors2: string[];
  };
  relationship_path: string[];
}

class EntityService {
  private baseUrl = process.env.REACT_APP_GRAPH_SERVICE_URL || 'http://localhost:8003';

  /**
   * Get entity by ID - backend retrieves with all metadata
   */
  async getEntity(entityId: string): Promise<GraphNode> {
    const response = await apiClient.get<GraphNode>(
      `${this.baseUrl}/entities/${entityId}`
    );
    return response.data;
  }

  /**
   * Update entity - backend validates and persists changes
   */
  async updateEntity(entityId: string, updates: EntityUpdateRequest): Promise<GraphNode> {
    const response = await apiClient.put<GraphNode>(
      `${this.baseUrl}/entities/${entityId}`,
      updates
    );
    return response.data;
  }

  /**
   * Delete entity - backend handles cascading deletions
   */
  async deleteEntity(entityId: string): Promise<void> {
    await apiClient.delete(`${this.baseUrl}/entities/${entityId}`);
  }

  /**
   * Get entity relationships - backend computes relationship strength
   */
  async getEntityRelationships(
    entityId: string,
    relationshipType?: string,
    limit: number = 50
  ): Promise<GraphEdge[]> {
    const response = await apiClient.get<{ relationships: GraphEdge[] }>(
      `${this.baseUrl}/entities/${entityId}/relationships`,
      {
        params: {
          relationship_type: relationshipType,
          limit,
          include_metadata: true,
          sort_by: 'weight',
          sort_order: 'desc'
        }
      }
    );
    return response.data.relationships;
  }

  /**
   * Add relationship between entities - backend validates relationship
   */
  async addRelationship(
    sourceId: string,
    targetId: string,
    relationship: RelationshipUpdateRequest
  ): Promise<GraphEdge> {
    const response = await apiClient.post<GraphEdge>(
      `${this.baseUrl}/relationships`,
      {
        source_id: sourceId,
        target_id: targetId,
        ...relationship
      }
    );
    return response.data;
  }

  /**
   * Update relationship - backend handles relationship modifications
   */
  async updateRelationship(
    relationshipId: string,
    updates: RelationshipUpdateRequest
  ): Promise<GraphEdge> {
    const response = await apiClient.put<GraphEdge>(
      `${this.baseUrl}/relationships/${relationshipId}`,
      updates
    );
    return response.data;
  }

  /**
   * Delete relationship - backend handles cleanup
   */
  async deleteRelationship(relationshipId: string): Promise<void> {
    await apiClient.delete(`${this.baseUrl}/relationships/${relationshipId}`);
  }

  /**
   * Get entity timeline - backend constructs event history
   */
  async getEntityTimeline(entityId: string): Promise<EntityTimeline> {
    const response = await apiClient.get<EntityTimeline>(
      `${this.baseUrl}/entities/${entityId}/timeline`,
      {
        params: {
          include_relationship_events: true,
          limit: 100
        }
      }
    );
    return response.data;
  }

  /**
   * Compare two entities - backend computes similarity metrics
   */
  async compareEntities(entity1Id: string, entity2Id: string): Promise<EntityComparison> {
    const response = await apiClient.post<EntityComparison>(
      `${this.baseUrl}/entities/compare`,
      {
        entity1_id: entity1Id,
        entity2_id: entity2Id,
        include_relationships: true,
        include_metadata: true
      }
    );
    return response.data;
  }

  /**
   * Find similar entities - backend performs similarity search
   */
  async findSimilarEntities(
    entityId: string,
    limit: number = 10,
    similarityThreshold: number = 0.5
  ): Promise<Array<{ entity: GraphNode; similarity: number }>> {
    const response = await apiClient.post<{
      similar_entities: Array<{ entity: GraphNode; similarity: number }>;
    }>(
      `${this.baseUrl}/entities/${entityId}/similar`,
      {
        limit,
        similarity_threshold: similarityThreshold,
        similarity_metrics: ['jaccard', 'cosine']
      }
    );
    return response.data.similar_entities;
  }

  /**
   * Get entity mentions in documents - backend extracts and ranks mentions
   */
  async getEntityMentions(
    entityId: string,
    limit: number = 20
  ): Promise<Array<{
    documentId: string;
    documentTitle: string;
    snippet: string;
    pageNumber?: number;
    confidence: number;
    context: string;
  }>> {
    const response = await apiClient.get<{
      mentions: Array<{
        documentId: string;
        documentTitle: string;
        snippet: string;
        pageNumber?: number;
        confidence: number;
        context: string;
      }>;
    }>(
      `${this.baseUrl}/entities/${entityId}/mentions`,
      {
        params: {
          limit,
          include_snippet: true,
          include_context: true,
          min_confidence: 0.3
        }
      }
    );
    return response.data.mentions;
  }

  /**
   * Get entity type statistics - backend aggregates type metrics
   */
  async getEntityTypeStats(): Promise<{
    type: string;
    count: number;
    avgConfidence: number;
    avgRelationships: number;
  }[]> {
    const response = await apiClient.get<{
      stats: {
        type: string;
        count: number;
        avgConfidence: number;
        avgRelationships: number;
      }[];
    }>(
      `${this.baseUrl}/entities/stats/types`
    );
    return response.data.stats;
  }

  /**
   * Merge entities - backend handles entity consolidation
   */
  async mergeEntities(
    primaryEntityId: string,
    secondaryEntityIds: string[],
    mergeStrategy: 'keep_primary' | 'merge_metadata' | 'create_new' = 'keep_primary'
  ): Promise<GraphNode> {
    const response = await apiClient.post<GraphNode>(
      `${this.baseUrl}/entities/merge`,
      {
        primary_entity_id: primaryEntityId,
        secondary_entity_ids: secondaryEntityIds,
        merge_strategy: mergeStrategy
      }
    );
    return response.data;
  }

  /**
   * Split entity - backend handles entity division
   */
  async splitEntity(
    entityId: string,
    splitCriteria: Record<string, any>
  ): Promise<GraphNode[]> {
    const response = await apiClient.post<{ entities: GraphNode[] }>(
      `${this.baseUrl}/entities/${entityId}/split`,
      {
        split_criteria: splitCriteria
      }
    );
    return response.data.entities;
  }
}

export const entityService = new EntityService();