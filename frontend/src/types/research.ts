/**
 * TypeScript types for Research Assistant feature
 */

// ============================================================================
// Citation Types
// ============================================================================

export interface CitationCreate {
  messageId?: string;
  documentId?: string;
  externalReferenceId?: string;
  documentTitle: string;
  documentType?: string;
  authors?: string[];
  year?: number;
  venue?: string;
  doi?: string;
  arxivId?: string;
  abstract?: string;
  snippet?: string;
  pageNumber?: number;
  score?: number;
  metadataSource?: 'manual' | 'arxiv' | 'crossref' | 'semantic_scholar' | 'rag';
  needsReview?: boolean;
}

export interface CitationResponse {
  id: string;
  messageId?: string;
  documentId?: string;
  externalReferenceId?: string;
  documentTitle: string;
  documentType: string;
  authors?: string[];
  year?: number;
  venue?: string;
  doi?: string;
  arxivId?: string;
  abstract?: string;
  snippet?: string;
  pageNumber?: number;
  score: number;
  metadataSource: string;
  needsReview: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface CitationListResponse {
  citations: CitationResponse[];
  total: number;
  skip: number;
  limit: number;
}

// ============================================================================
// Project Types
// ============================================================================

export interface ProjectCreate {
  name: string;
  description?: string;
  projectType?: 'research' | 'literature_review' | 'thesis' | 'paper';
  researchStatus?: 'active' | 'paused' | 'completed' | 'archived';
  researchGoals?: string;
  deadline?: string;
  tags?: string[];
}

export interface ProjectResponse {
  id: string;
  userId: string;
  name: string;
  description?: string;
  projectType: string;
  researchStatus: string;
  researchGoals?: string;
  deadline?: string;
  tags: string[];
  isPrivate: boolean;
  createdAt: string;
  updatedAt: string;
}

// ============================================================================
// Note Types
// ============================================================================

export interface NoteCreate {
  projectId: string;
  title: string;
  content: string;
  linkedDocumentIds?: string[];
  tags?: string[];
  isPinned?: boolean;
}

export interface NoteResponse {
  id: string;
  projectId: string;
  userId: string;
  title: string;
  content: string;
  linkedDocumentIds: string[];
  tags: string[];
  isPinned: boolean;
  createdAt: string;
  updatedAt: string;
}

// ============================================================================
// Draft Types
// ============================================================================

export interface DraftGenerateRequest {
  themes: string[];
  documentIds?: string[];
  style?: 'academic' | 'technical' | 'summary';
  maxSections?: number;
  includeAbstract?: boolean;
}

export interface DraftResponse {
  id: string;
  projectId: string;
  version: number;
  title: string;
  content: string;
  themes: string[];
  wordCount?: number;
  citationCount?: number;
  generationParams: Record<string, any>;
  generationTimeMs?: number;
  isCurrent: boolean;
  createdAt: string;
}

export interface DraftComparisonResponse {
  versionA: DraftResponse;
  versionB: DraftResponse;
  wordCountDiff: number;
  similarityScore: number;
}
