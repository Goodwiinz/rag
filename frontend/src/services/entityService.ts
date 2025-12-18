/**
 * Entity Service - API Client for Entity Operations
 *
 * Handles entity CRUD operations, relationship management,
 * and entity-specific data consumption from backend.
 */

import { Entity, EntityResponse, GraphEdge } from '@/types/entity';
import { apiClient } from './apiClient';

export interface EntityUpdateRequest {
  name?: string;
  confidence_score?: number;
  metadata?: Record<string, any>;
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
   * Get all entities
   */
  async getEntities(limit: number = 100, offset: number = 0): Promise<EntityResponse[]> {
    try {
      const response = await apiClient.get(`${this.baseUrl}/entities`, {
        params: { limit, offset }
      });
      console.log('Entities API response:', response);
      console.log('Entities API response:', response);
      return (response as any) || [];
    } catch (error) {
      console.error('Error in getEntities:', error);
      throw error;
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
}

export const entityService = new EntityService();