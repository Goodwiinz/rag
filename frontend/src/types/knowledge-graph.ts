// Knowledge Graph Types
export interface KnowledgeGraphData {
  nodes: import('./search').Entity[];
  edges: import('./search').Relationship[];
  layout: 'force' | 'hierarchical' | 'circular';
  filters: {
    entity_types?: import('./search').Entity['type'][];
    min_confidence?: number;
    date_range?: {
      start: string;
      end: string;
    };
  };
}

export interface GraphNodeInteraction {
  node_id: string;
  action: 'click' | 'hover' | 'select';
  timestamp: string;
  related_nodes: string[];
  context: {
    query_id?: string;
    search_context?: string;
  };
}

export interface GraphFilters {
  entity_types: import('./search').Entity['type'][];
  relationship_types: string[];
  min_confidence: number;
  date_range?: {
    start: string;
    end: string;
  };
  document_ids?: string[];
}

export interface EntityDetails {
  entity: import('./search').Entity;
  relationships: import('./search').Relationship[];
  documents: import('./document').Document[];
  related_entities: Array<{
    entity: import('./search').Entity;
    relationship: import('./search').Relationship;
    strength: number;
  }>;
  mention_contexts: Array<{
    document_id: string;
    snippet: string;
    page_number?: number;
    confidence: number;
  }>;
}

