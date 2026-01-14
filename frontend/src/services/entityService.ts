/**
 * Entity Service - API Client for Entity Operations
 *
 * Handles entity CRUD operations, relationship management,
 * and entity-specific data consumption from backend.
 */

import { Entity, EntityResponse, EntityType, GraphEdge } from '@/types/entity';
import { EntityDetails, GraphNode } from '@/types/graph-api';
import { apiClient } from './apiClient';

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

class EntityService {
  private baseUrl = 'knowledge-graph';

  /**
   * Get all entities with pagination
   */
  async getEntities(
    limit: number = 100, 
    offset: number = 0,
    entityTypes?: EntityType[]
  ): Promise<PaginatedEntitiesResponse> {
    try {
      const params: Record<string, any> = { limit, offset };
      if (entityTypes && entityTypes.length > 0) {
        params.entity_types = entityTypes;
      }
      const response = await apiClient.get(`${this.baseUrl}/entities`, { params });
      return response as PaginatedEntitiesResponse;
    } catch (error) {
      console.error('Error in getEntities:', error);
      throw error;
    }
  }

  /**
   * Get all relationships
   */
  async getAllRelationships(limit: number = 500, offset: number = 0): Promise<GraphEdge[]> {
    try {
      const response = await apiClient.get(`${this.baseUrl}/relationships`, {
        params: { limit, offset }
      });
      // Transform backend response to GraphEdge format
      const relationships = (response as any[]) || [];
      return relationships.map(rel => ({
        id: rel.id,
        source: rel.source_entity_id,
        target: rel.target_entity_id,
        type: rel.relationship_type,
        weight: rel.strength,
        strength: rel.strength,
        confidence: rel.confidence_score,
        context: rel.context,
        metadata: rel.metadata
      }));
    } catch (error) {
      console.error('Error in getAllRelationships:', error);
      return [];
    }
  }

  /**
   * Get entity by ID - backend retrieves with all metadata
   */
  async getEntity(entityId: string): Promise<Entity> {
    const response = await apiClient.get<Entity>(
      `${this.baseUrl}/entities/${entityId}`
    );
    return response;
  }

  /**
   * Create new entity
   */
  async createEntity(entityData: Partial<Entity>): Promise<Entity> {
    const response = await apiClient.post<Entity>(
      `${this.baseUrl}/entities`,
      entityData
    );
    return response;
  }

  /**
   * Update entity - backend validates and persists changes
   */
  async updateEntity(entityId: string, updates: EntityUpdateRequest): Promise<Entity> {
    const response = await apiClient.put<Entity>(
      `${this.baseUrl}/entities/${entityId}`,
      updates
    );
    return response;
  }

  /**
   * Delete entity - backend handles cascading deletions
   */
  async deleteEntity(entityId: string): Promise<void> {
    await apiClient.delete(`${this.baseUrl}/entities/${entityId}`);
  }

  /**
   * Search entities
   */
  async searchEntities(
    query: string,
    entityTypes?: string[],
    limit: number = 50
  ): Promise<Entity[]> {
    const response = await apiClient.get<Entity[]>(
      `${this.baseUrl}/entities/search`,
      {
        params: { query, entity_types: entityTypes, limit }
      }
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
    const response = await apiClient.get<GraphEdge[]>(
      `${this.baseUrl}/entities/${entityId}/relationships`,
      {
        params: {
          relationship_type: relationshipType,
          limit
        }
      }
    );
    return response;
  }

  /**
   * Create relationship between entities
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
    const response = await apiClient.post<GraphEdge>(
      `${this.baseUrl}/relationships`,
      relationshipData
    );
    return response;
  }

  /**
   * Delete relationship
   */
  async deleteRelationship(relationshipId: string): Promise<void> {
    await apiClient.delete(`${this.baseUrl}/relationships/${relationshipId}`);
  }

  /**
   * Get entity details with extended metadata, relationships, and documents
   */
  async getEntityDetails(entityId: string): Promise<EntityDetails> {
    const response = await apiClient.get<EntityDetails>(
      `${this.baseUrl}/entities/${entityId}/details`
    );
    return response;
  }

  /**
   * Find similar entities based on embedding similarity
   */
  async findSimilarEntities(
    entityId: string,
    limit: number = 10,
    minSimilarity: number = 0.5
  ): Promise<Array<{ entity: GraphNode; similarity: number }>> {
    const response = await apiClient.get<Array<{ entity: GraphNode; similarity: number }>>(
      `${this.baseUrl}/entities/${entityId}/similar`,
      {
        params: { limit, min_similarity: minSimilarity }
      }
    );
    return response;
  }

  /**
   * Get entity timeline events
   */
  async getEntityTimeline(entityId: string): Promise<EntityTimeline> {
    const response = await apiClient.get<EntityTimeline>(
      `${this.baseUrl}/entities/${entityId}/timeline`
    );
    return response;
  }

  /**
   * Get all available entity types from the backend
   */
  async getEntityTypes(): Promise<string[]> {
    try {
      const response = await apiClient.get<string[]>(
        `${this.baseUrl}/entity-types`
      );
      return response;
    } catch (error) {
      console.error('Error fetching entity types:', error);
      // Return fallback hardcoded types if API fails
      return [
        'PERSON', 'ORGANIZATION', 'LOCATION', 'CONCEPT', 'EVENT',
        'PRODUCT', 'DATE', 'TECHNOLOGY', 'DOCUMENT', 'OTHER'
      ];
    }
  }

  /**
   * Get all available relationship types from the backend
   */
  async getRelationshipTypes(): Promise<string[]> {
    try {
      const response = await apiClient.get<string[]>(
        `${this.baseUrl}/relationship-types`
      );
      return response;
    } catch (error) {
      console.error('Error fetching relationship types:', error);
      // Return fallback hardcoded types if API fails
      return [
        'WORKS_FOR', 'LOCATED_IN', 'KNOWS', 'RELATED_TO', 'PART_OF',
        'OWNS', 'CREATED_BY', 'USES', 'MANAGES', 'COLLABORATES_WITH'
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
      const response = await apiClient.get(
        `${this.baseUrl}/visualization/${entityId}`,
        {
          params: { depth, max_nodes: maxNodes }
        }
      );
      return response;
    } catch (error) {
      console.error('Error fetching visualization data:', error);
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
      const response = await apiClient.post(
        `${this.baseUrl}/search`,
        params
      );
      return response;
    } catch (error) {
      console.error('Error performing graph search:', error);
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
      const response = await apiClient.post(
        `${this.baseUrl}/batch`,
        params
      );
      return response;
    } catch (error) {
      console.error('Error in batch create:', error);
      throw error;
    }
  }
}

export const entityService = new EntityService();