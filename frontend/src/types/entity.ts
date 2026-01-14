/**
 * Entity Types for RAG System
 */

export type EntityType =
  | 'PERSON'
  | 'ORGANIZATION'
  | 'LOCATION'
  | 'CONCEPT'
  | 'EVENT'
  | 'PRODUCT'
  | 'DATE'
  | 'TECHNOLOGY'
  | 'DOCUMENT';

export type RelationshipType =
  | 'WORKS_FOR'
  | 'LOCATED_IN'
  | 'KNOWS'
  | 'RELATED_TO'
  | 'PART_OF'
  | 'OWNS'
  | 'CREATED_BY'
  | 'USES'
  | 'MANAGES'
  | 'COLLABORATES_WITH'
  | 'MEMBER_OF'
  | 'FOUND_IN'
  | 'EXAMPLE_OF'
  | 'CAUSES'
  | 'ENABLES'
  | 'REQUIRES'
  | 'PRECEDES'
  | 'FOLLOWS';

export interface Entity {
  id: string;
  name: string;
  type: EntityType;
  confidence?: number;
  confidence_score?: number;
  extraction_method?: string;
  position?: {
    start: number;
    end: number;
  };
  context?: string;
  metadata?: Record<string, any>;
  source_document_id?: string;
  created_at: string;
  updated_at?: string;
  user_id?: string;
  organization_id?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  weight?: number;
  strength?: number;
  confidence?: number;
  confidence_score?: number;
  context?: string;
  evidence?: string[];
  metadata?: Record<string, any>;
  source_document_id?: string;
  created_at?: string;
  updated_at?: string;
}

export interface EntityResponse {
  id: string;
  name: string;
  entity_type: EntityType;
  confidence_score: number;
  extraction_method: string;
  position?: {
    start: number;
    end: number;
  };
  context?: string;
  metadata: Record<string, any>;
  source_document_id?: string;
  created_at: string;
  updated_at?: string;
}

export interface CreateEntityRequest {
  name: string;
  type: EntityType;
  confidence_score?: number;
  metadata?: Record<string, any>;
}

export interface UpdateEntityRequest {
  name?: string;
  confidence_score?: number;
  metadata?: Record<string, any>;
}

export interface RelationshipResponse {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  relationship_type: RelationshipType;
  strength: number;
  confidence_score: number;
  context?: string;
  evidence: string[];
  metadata: Record<string, any>;
  source_document_id?: string;
  created_at: string;
  updated_at?: string;
}

export interface CreateRelationshipRequest {
  source_entity_id: string;
  target_entity_id: string;
  relationship_type: RelationshipType;
  strength?: number;
  confidence_score?: number;
  context?: string;
  evidence?: string[];
  metadata?: Record<string, any>;
  source_document_id?: string;
}

export interface GraphSearchRequest {
  query: string;
  entity_types?: EntityType[];
  relationship_types?: RelationshipType[];
  max_results?: number;
  max_depth?: number;
  min_strength?: number;
}

export interface GraphSearchResponse {
  query: string;
  entities: EntityResponse[];
  relationships: RelationshipResponse[];
  paths: GraphPath[];
  total_entities: number;
  total_relationships: number;
  total_paths: number;
  search_time: number;
}

export interface GraphPath {
  id: string;
  source_id: string;
  target_id: string;
  path_length: number;
  total_strength: number;
  entities: string[];
  relationships: string[];
}

/**
 * Duplicate detection result for entity creation
 */
export interface DuplicateCheckResult {
  isDuplicate: boolean;
  existingEntities: Entity[];
  suggestedName?: string; // e.g., "John Smith (2)"
}

/**
 * Authorization permissions for entity operations
 */
export interface EntityPermissions {
  canCreate: boolean;
  canEdit: boolean;
  canDelete: boolean;
  canBulkEdit: boolean;
  isAdmin: boolean;
}

/**
 * Entity type option with count for filter dropdown
 */
export interface EntityTypeOption {
  value: string;
  label: string;
  count: number;
  isSpecial?: boolean; // For special filters like null type
}