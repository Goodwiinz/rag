/**
 * Project Service
 * API client for Research Assistant project endpoints
 */

import { apiClient } from './apiClient';

// Types
export interface Project {
  id: string;
  name: string;
  description?: string;
  user_id: string;
  created_at: string;
  updated_at: string;
  document_count?: number;
  citation_count?: number;
  note_count?: number;
}

export interface ProjectCreate {
  name: string;
  description?: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
}

export interface ProjectDocument {
  id: string;
  project_id: string;
  document_id: string;
  added_at: string;
  document?: {
    id: string;
    title: string;
    filename: string;
    status: string;
    created_at: string;
  };
}

export interface ProjectNote {
  id: string;
  project_id: string;
  title: string;
  content: string;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectNoteCreate {
  title: string;
  content: string;
}

export interface ProjectNoteUpdate {
  title?: string;
  content?: string;
}

export interface ProjectListResponse {
  projects: Project[];
  total: number;
  skip: number;
  limit: number;
}

export interface ProjectDocumentListResponse {
  documents: ProjectDocument[];
  total: number;
}

export interface ProjectNoteListResponse {
  notes: ProjectNote[];
  total: number;
}

export interface ProjectBibliography {
  project_id: string;
  project_name: string;
  format: string;
  content: string;
  citation_count: number;
  generated_at: string;
}

export const projectService = {
  // =========================================================================
  // Project CRUD (T061)
  // =========================================================================

  /**
   * List all projects for current user
   */
  async listProjects(params?: {
    skip?: number;
    limit?: number;
    search?: string;
  }): Promise<ProjectListResponse> {
    const response = await apiClient.get<ProjectListResponse>('/projects', {
      params,
    });
    return response.data;
  },

  /**
   * Create a new project
   */
  async createProject(data: ProjectCreate): Promise<Project> {
    const response = await apiClient.post<Project>('/projects', data);
    return response.data;
  },

  /**
   * Get a single project by ID
   */
  async getProject(projectId: string): Promise<Project> {
    const response = await apiClient.get<Project>(`/projects/${projectId}`);
    return response.data;
  },

  /**
   * Update a project
   */
  async updateProject(projectId: string, data: ProjectUpdate): Promise<Project> {
    const response = await apiClient.patch<Project>(`/projects/${projectId}`, data);
    return response.data;
  },

  /**
   * Delete a project
   */
  async deleteProject(projectId: string): Promise<void> {
    await apiClient.delete(`/projects/${projectId}`);
  },

  // =========================================================================
  // Project Documents (T062)
  // =========================================================================

  /**
   * List documents in a project
   */
  async listProjectDocuments(
    projectId: string,
    params?: {
      skip?: number;
      limit?: number;
    }
  ): Promise<ProjectDocumentListResponse> {
    const response = await apiClient.get<ProjectDocumentListResponse>(
      `/projects/${projectId}/documents`,
      { params }
    );
    return response.data;
  },

  /**
   * Add a document to a project
   */
  async addDocumentToProject(
    projectId: string,
    documentId: string
  ): Promise<ProjectDocument> {
    const response = await apiClient.post<ProjectDocument>(
      `/projects/${projectId}/documents`,
      null,
      { params: { document_id: documentId } }
    );
    return response.data;
  },

  /**
   * Remove a document from a project
   */
  async removeDocumentFromProject(
    projectId: string,
    documentId: string
  ): Promise<void> {
    await apiClient.delete(`/projects/${projectId}/documents/${documentId}`);
  },

  // =========================================================================
  // Project Notes (T063)
  // =========================================================================

  /**
   * List notes in a project
   */
  async listProjectNotes(
    projectId: string,
    params?: {
      skip?: number;
      limit?: number;
      pinned_only?: boolean;
    }
  ): Promise<ProjectNoteListResponse> {
    const response = await apiClient.get<ProjectNoteListResponse>(
      `/projects/${projectId}/notes`,
      { params }
    );
    return response.data;
  },

  /**
   * Create a note in a project
   */
  async createNote(projectId: string, data: ProjectNoteCreate): Promise<ProjectNote> {
    const response = await apiClient.post<ProjectNote>(
      `/projects/${projectId}/notes`,
      data
    );
    return response.data;
  },

  /**
   * Get a single note
   */
  async getNote(projectId: string, noteId: string): Promise<ProjectNote> {
    const response = await apiClient.get<ProjectNote>(
      `/projects/${projectId}/notes/${noteId}`
    );
    return response.data;
  },

  /**
   * Update a note
   */
  async updateNote(
    projectId: string,
    noteId: string,
    data: ProjectNoteUpdate
  ): Promise<ProjectNote> {
    const response = await apiClient.patch<ProjectNote>(
      `/projects/${projectId}/notes/${noteId}`,
      data
    );
    return response.data;
  },

  /**
   * Delete a note
   */
  async deleteNote(projectId: string, noteId: string): Promise<void> {
    await apiClient.delete(`/projects/${projectId}/notes/${noteId}`);
  },

  /**
   * Toggle note pinned status
   */
  async toggleNotePin(projectId: string, noteId: string): Promise<ProjectNote> {
    const response = await apiClient.post<ProjectNote>(
      `/projects/${projectId}/notes/${noteId}/pin`
    );
    return response.data;
  },

  // =========================================================================
  // Project Bibliography (T064)
  // =========================================================================

  /**
   * Get project bibliography in specified format
   */
  async getProjectBibliography(
    projectId: string,
    format: 'bibtex' | 'ieee' | 'apa' | 'mla' = 'bibtex'
  ): Promise<ProjectBibliography> {
    const response = await apiClient.get<ProjectBibliography>(
      `/projects/${projectId}/bibliography`,
      { params: { format } }
    );
    return response.data;
  },

  /**
   * Download project bibliography as file
   */
  async downloadBibliography(
    projectId: string,
    format: 'bibtex' | 'ieee' | 'apa' | 'mla' = 'bibtex',
    filename?: string
  ): Promise<void> {
    const bibliography = await this.getProjectBibliography(projectId, format);

    // Create blob and download
    const blob = new Blob([bibliography.content], {
      type: format === 'bibtex' ? 'application/x-bibtex' : 'text/plain',
    });

    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename || `${bibliography.project_name}-bibliography.${format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },

  // =========================================================================
  // Draft Generation (T089)
  // =========================================================================

  /**
   * Generate a literature review draft
   */
  async generateDraft(
    projectId: string,
    themes: string[],
    options?: {
      documentIds?: string[];
      style?: 'academic' | 'technical' | 'summary';
      maxSections?: number;
      includeAbstract?: boolean;
    }
  ): Promise<DraftGenerationResponse> {
    const params = new URLSearchParams();
    themes.forEach((t) => params.append('themes', t));
    if (options?.documentIds) {
      options.documentIds.forEach((id) => params.append('document_ids', id));
    }
    if (options?.style) params.append('style', options.style);
    if (options?.maxSections) params.append('max_sections', options.maxSections.toString());
    if (options?.includeAbstract !== undefined) {
      params.append('include_abstract', options.includeAbstract.toString());
    }

    const response = await apiClient.post<DraftGenerationResponse>(
      `/projects/${projectId}/drafts?${params.toString()}`
    );
    return response.data;
  },

  /**
   * List drafts for a project
   */
  async listDrafts(
    projectId: string,
    options?: {
      includeContent?: boolean;
      skip?: number;
      limit?: number;
    }
  ): Promise<DraftListResponse> {
    const response = await apiClient.get<DraftListResponse>(
      `/projects/${projectId}/drafts`,
      { params: options }
    );
    return response.data;
  },

  /**
   * Get the current draft
   */
  async getCurrentDraft(projectId: string): Promise<Draft> {
    const response = await apiClient.get<Draft>(
      `/projects/${projectId}/drafts/current`
    );
    return response.data;
  },

  /**
   * Get a specific draft
   */
  async getDraft(projectId: string, draftId: string): Promise<Draft> {
    const response = await apiClient.get<Draft>(
      `/projects/${projectId}/drafts/${draftId}`
    );
    return response.data;
  },

  /**
   * Delete a draft
   */
  async deleteDraft(projectId: string, draftId: string): Promise<void> {
    await apiClient.delete(`/projects/${projectId}/drafts/${draftId}`);
  },

  /**
   * Get draft citations
   */
  async getDraftCitations(projectId: string, draftId: string): Promise<DraftCitationsResponse> {
    const response = await apiClient.get<DraftCitationsResponse>(
      `/projects/${projectId}/drafts/${draftId}/citations`
    );
    return response.data;
  },

  /**
   * Compare two draft versions
   */
  async compareDrafts(
    projectId: string,
    versionA: number,
    versionB: number
  ): Promise<DraftComparison> {
    const response = await apiClient.get<DraftComparison>(
      `/projects/${projectId}/drafts/compare`,
      { params: { version_a: versionA, version_b: versionB } }
    );
    return response.data;
  },

  /**
   * Export draft to file format
   */
  async exportDraft(
    projectId: string,
    draftId: string,
    format: 'markdown' | 'latex' = 'markdown',
    includeBibliography: boolean = true
  ): Promise<DraftExportResponse> {
    const response = await apiClient.post<DraftExportResponse>(
      `/projects/${projectId}/drafts/${draftId}/export`,
      null,
      {
        params: {
          format,
          include_bibliography: includeBibliography,
        },
      }
    );
    return response.data;
  },

  /**
   * Get generation status
   */
  async getGenerationStatus(projectId: string, taskId: string): Promise<GenerationStatus> {
    const response = await apiClient.get<GenerationStatus>(
      `/projects/${projectId}/drafts/status/${taskId}`
    );
    return response.data;
  },

  /**
   * Cancel ongoing generation
   */
  async cancelGeneration(projectId: string, taskId: string): Promise<void> {
    await apiClient.post(`/projects/${projectId}/drafts/cancel/${taskId}`);
  },
};

// Draft types
export interface Draft {
  id: string;
  project_id: string;
  version: number;
  title: string;
  content: string;
  themes: string[];
  word_count: number;
  citation_count: number;
  generation_params?: Record<string, unknown>;
  is_current: boolean;
  created_at: string;
}

export interface DraftListResponse {
  drafts: Omit<Draft, 'content'>[];
  total: number;
  skip: number;
  limit: number;
}

export interface DraftGenerationResponse {
  task_id: string;
  status: string;
  message: string;
}

export interface GenerationStatus {
  status: string;
  progress: number;
  current_step: string;
  started_at: string;
  updated_at?: string;
  estimated_remaining?: number;
  draft_id?: string;
  duration?: number;
}

export interface DraftCitation {
  id: string;
  citation_index: number;
  document_id?: string;
  citation_id?: string;
  snippet: string;
  context: string;
}

export interface DraftCitationsResponse {
  citations: DraftCitation[];
  total: number;
}

export interface DraftComparison {
  version_a: {
    version: number;
    word_count: number;
    citation_count: number;
    created_at: string;
  };
  version_b: {
    version: number;
    word_count: number;
    citation_count: number;
    created_at: string;
  };
  word_count_diff: number;
  citation_count_diff: number;
  similarity_score: number;
}

export interface DraftExportResponse {
  format: string;
  filename?: string;
  content?: string;
  mime_type?: string;
  files?: Array<{
    filename: string;
    content: string;
    mime_type: string;
  }>;
}

export default projectService;
