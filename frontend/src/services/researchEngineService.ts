import { apiClient } from '@/services/apiClient';

const BASE = '/research-engine';

// Types
export interface ProjectCreate {
  name: string;
  description?: string;
  settings?: Record<string, unknown>;
}

export interface BlueprintStepDef {
  type: string;
  name: string;
  description?: string;
  parameters: Record<string, unknown>;
  model_id?: string;
  model_version?: string;
  mode: 'deterministic' | 'exploratory';
  temperature?: number;
  seed?: number;
}

export interface BlueprintCreate {
  name: string;
  template_source?: string;
  steps: BlueprintStepDef[];
  parameters: Record<string, unknown>;
}

// Functions
export const listProjects = () => apiClient.get(`${BASE}/projects`);

export const createProject = (data: ProjectCreate) =>
  apiClient.post(`${BASE}/projects`, data);

export const getProject = (id: string) =>
  apiClient.get(`${BASE}/projects/${id}`);

export const listTemplates = () =>
  apiClient.get(`${BASE}/blueprints/templates`);

export const createBlueprint = (projectId: string, data: BlueprintCreate) =>
  apiClient.post(`${BASE}/blueprints/projects/${projectId}`, data);

export const getBlueprint = (id: string) =>
  apiClient.get(`${BASE}/blueprints/${id}`);

export const startRun = (
  blueprintId: string,
  parametersOverride: Record<string, unknown>
) =>
  apiClient.post(`${BASE}/blueprints/${blueprintId}/runs`, {
    parameters_override: parametersOverride,
  });

export const getRun = (runId: string) => apiClient.get(`${BASE}/runs/${runId}`);

export const pauseRun = (runId: string) =>
  apiClient.post(`${BASE}/runs/${runId}/pause`);

export const resumeRun = (runId: string) =>
  apiClient.post(`${BASE}/runs/${runId}/resume`);

export const getRunManifest = (runId: string) =>
  apiClient.get(`${BASE}/runs/${runId}/manifest`);

export const listSteps = (runId: string) =>
  apiClient.get(`${BASE}/runs/${runId}/steps`);

export const getStep = (stepId: string) =>
  apiClient.get(`${BASE}/steps/${stepId}`);
