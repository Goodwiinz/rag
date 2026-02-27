/**
 * TypeScript types for SciSpace integration features.
 * Mirrors backend schemas from backend/src/shared/scispace_schemas.py
 */

// ============================================================================
// Feature 1: Extraction Matrix
// ============================================================================

export interface ExtractionColumn {
  name: string;
  description?: string;
}

export interface ExtractionCell {
  document_id: string;
  column_name: string;
  value: string | null;
  citation_snippet: string | null;
  confidence: number | null;
}

export interface ExtractionMatrix {
  id: string;
  project_id: string;
  name: string;
  columns: ExtractionColumn[];
  cells: ExtractionCell[];
  created_at: string | null;
  updated_at: string | null;
}

export interface CreateMatrixRequest {
  name: string;
  columns: ExtractionColumn[];
}

export interface TriggerExtractionRequest {
  document_ids: string[];
}

export interface TriggerExtractionResponse {
  matrix_id: string;
  document_ids: string[];
  status: string;
  message: string;
}

// ============================================================================
// Feature 2: Table/Math Extraction
// ============================================================================

export interface ExtractedTable {
  page: number;
  table_index: number;
  rows: string[][];
  markdown: string;
  method: string;
}

export interface TablesResponse {
  document_id: string;
  table_count: number;
  tables: ExtractedTable[];
}

export interface ExtractRegionRequest {
  page: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface ExtractRegionResponse {
  document_id: string;
  page: number;
  region: { x1: number; y1: number; x2: number; y2: number };
  format: 'csv' | 'latex' | 'markdown';
  content: string;
  confidence: number;
}

// ============================================================================
// Feature 3: Tone Engine
// ============================================================================

export type ToneOption = 'academic' | 'simplified' | 'concise' | 'expanded';

export interface RewriteRequest {
  text: string;
  tone: ToneOption;
  preserve_citations?: boolean;
  model?: string;
}

export interface RewriteResponse {
  original: string;
  rewritten: string;
  tone_applied: ToneOption;
  citations_preserved: string[];
}

// ============================================================================
// Feature 4: Source Connectors
// ============================================================================

export type SourceConnectorType =
  | 'arxiv'
  | 'semantic_scholar'
  | 'crossref'
  | 'pubmed';

export interface SourceConnectorOption {
  id: SourceConnectorType;
  label: string;
  description: string;
  icon: string;
}

// ============================================================================
// Feature 5: Integrity Detector
// ============================================================================

export interface IntegritySegmentScore {
  text_preview: string;
  ai_probability: number;
}

export interface IntegrityScoreResponse {
  document_id: string;
  ai_probability: number;
  human_probability: number;
  method: string;
  analyzed_at: string | null;
  segment_scores: IntegritySegmentScore[];
}

export interface IntegrityCheckResponse {
  document_id: string;
  status: string;
  ai_probability: number;
  human_probability: number;
  method: string;
  analyzed_at: string;
}

export type IntegrityLevel = 'human' | 'mixed' | 'ai';

export function getIntegrityLevel(aiProbability: number): IntegrityLevel {
  if (aiProbability < 0.3) return 'human';
  if (aiProbability <= 0.7) return 'mixed';
  return 'ai';
}
