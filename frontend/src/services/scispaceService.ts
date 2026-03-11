/**
 * SciSpace integration API service.
 * Handles all API calls for extraction matrix, table extraction,
 * tone engine, and integrity detection features.
 */

import { apiClient } from '@/services/apiClient';
import type {
  CreateMatrixRequest,
  CreateMatrixResponse,
  ExtractionMatrix,
  ExtractionTaskStatus,
  ExtractRegionRequest,
  ExtractRegionResponse,
  IntegrityCheckResponse,
  IntegrityScoreResponse,
  OutlineRequest,
  OutlineResponse,
  PipelineState,
  RewriteRequest,
  RewriteResponse,
  TablesResponse,
  TriggerExtractionRequest,
  TriggerExtractionResponse,
  UpdateMatrixRequest,
  UpdateMatrixResponse,
  UpdatePipelineRequest,
  WriteRequest,
  WriteResponse,
} from '@/types/scispace';

// ============================================================================
// Feature 1: Extraction Matrix
// ============================================================================

const RESEARCH_BASE = '/research';

export const listMatrices = (projectId: string) =>
  apiClient.get<{
    matrices: Array<{
      id: string;
      project_id: string;
      name: string;
      columns: CreateMatrixRequest['columns'];
      created_at: string;
    }>;
    total: number;
  }>(`${RESEARCH_BASE}/projects/${projectId}/matrices`);

export const createMatrix = (projectId: string, data: CreateMatrixRequest) =>
  apiClient.post<CreateMatrixResponse>(
    `${RESEARCH_BASE}/projects/${projectId}/matrices`,
    data
  );

export const getMatrix = (matrixId: string) =>
  apiClient.get<ExtractionMatrix>(`${RESEARCH_BASE}/matrices/${matrixId}`);

export const triggerExtraction = (
  matrixId: string,
  data: TriggerExtractionRequest
) =>
  apiClient.post<TriggerExtractionResponse>(
    `${RESEARCH_BASE}/matrices/${matrixId}/extract`,
    data
  );

export const updateMatrix = (matrixId: string, data: UpdateMatrixRequest) =>
  apiClient.patch<UpdateMatrixResponse>(
    `${RESEARCH_BASE}/matrices/${matrixId}`,
    data
  );

export const deleteMatrix = (matrixId: string) =>
  apiClient.delete<{ message: string; matrix_id: string }>(
    `${RESEARCH_BASE}/matrices/${matrixId}`
  );

export const getExtractionTaskStatus = (taskId: string) =>
  apiClient.get<ExtractionTaskStatus>(
    `${RESEARCH_BASE}/extraction-tasks/${taskId}`
  );

// ============================================================================
// Feature 2: Table/Math Extraction
// ============================================================================

const DOCUMENTS_BASE = '/documents';

export const extractTables = (documentId: string) =>
  apiClient.get<TablesResponse>(`${DOCUMENTS_BASE}/${documentId}/tables`);

export const extractRegion = (documentId: string, data: ExtractRegionRequest) =>
  apiClient.post<ExtractRegionResponse>(
    `${DOCUMENTS_BASE}/${documentId}/extract-region`,
    data
  );

// ============================================================================
// Feature 3: Tone Engine
// ============================================================================

export const rewriteText = (data: RewriteRequest) =>
  apiClient.post<RewriteResponse>(`${RESEARCH_BASE}/rewrite`, data);

// ============================================================================
// Feature 5: Integrity Detection
// ============================================================================

export const triggerIntegrityCheck = (documentId: string) =>
  apiClient.post<IntegrityCheckResponse>(
    `${DOCUMENTS_BASE}/${documentId}/integrity-check`
  );

export const getIntegrityScore = (documentId: string) =>
  apiClient.get<IntegrityScoreResponse>(
    `${DOCUMENTS_BASE}/${documentId}/integrity-score`
  );

// ============================================================================
// Feature 6: AI Writer
// ============================================================================

export const writeText = (data: WriteRequest) =>
  apiClient.postWithLongTimeout<WriteResponse>(`${RESEARCH_BASE}/write`, data);

export const generateOutline = (data: OutlineRequest) =>
  apiClient.postWithLongTimeout<OutlineResponse>(
    `${RESEARCH_BASE}/outline`,
    data
  );

// ============================================================================
// Feature 7: Research Pipeline
// ============================================================================

export const getPipeline = (projectId: string) =>
  apiClient.get<PipelineState>(
    `${RESEARCH_BASE}/projects/${projectId}/pipeline`
  );

export const updatePipeline = (
  projectId: string,
  data: UpdatePipelineRequest
) =>
  apiClient.patch<PipelineState>(
    `${RESEARCH_BASE}/projects/${projectId}/pipeline`,
    data
  );

export const resetPipeline = (projectId: string) =>
  apiClient.post<PipelineState>(
    `${RESEARCH_BASE}/projects/${projectId}/pipeline/reset`
  );
