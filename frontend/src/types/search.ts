// Search and Query Types
export interface SearchRequest {
  query: string;
  filters?: {
    modalities?: ('text' | 'image' | 'audio' | 'video')[];
    document_ids?: string[];
    date_range?: {
      start: string;
      end: string;
    };
    file_types?: import('./document').Document['file_type'][];
  };
  limit?: number;
  offset?: number;
}

export interface SourceReference {
  document_id: string;
  document_title: string;
  snippet: string;
  confidence: number;
  page_number?: number;
  timestamp?: string;
  file_type: import('./document').Document['file_type'];
  url?: string; // For direct document access
}

export interface SearchAnswer {
  text: string;
  sources: SourceReference[];
  confidence: number;
  answer_type: 'factual' | 'reasoning' | 'summarization' | 'comparison';
  language_detected: string;
}

export interface SearchResult {
  id: string;
  query: string;
  answer: SearchAnswer;
  entities: Entity[];
  relationships: Relationship[];
  metrics: SearchMetrics;
  processing_time_ms: number;
  created_at: string;
  user_id: string;
}

export interface SearchMetrics {
  latency_ms: number;
  retrieval_quality: number; // 0-100
  faithfulness_score: number; // 0-100
  contextual_relevancy: number; // 0-100
  hallucination_score: number; // 0-100
  answer_relevancy: number; // 0-100
  documents_retrieved: number;
  entities_found: number;
  relationships_found: number;
}

export interface QueryHistory {
  id: string;
  query: string;
  created_at: string;
  answer_preview: string; // First 100 characters
  has_answer: boolean;
  metrics: {
    latency_ms: number;
    quality_score: number;
  };
}

export interface QuerySuggestions {
  suggestions: string[];
  related_queries: Array<{
    query: string;
    similarity: number;
  }>;
  auto_complete: string[];
}

// Entity and Relationship Types (shared with knowledge graph)
export interface Entity {
  id: string;
  name: string;
  type: 'person' | 'organization' | 'location' | 'concept' | 'date' | 'product';
  confidence: number;
  description?: string;
  aliases: string[];
  mentions: number;
  first_seen: string;
  last_seen: string;
  document_ids: string[];
  metadata: Record<string, any>;
  position?: {
    x: number;
    y: number;
  };
  color?: string;
  size?: number;
}

export interface Relationship {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  relationship_type: string;
  confidence: number;
  context: string;
  document_ids: string[];
  first_seen: string;
  last_seen: string;
  weight: number;
  metadata: Record<string, any>;
}