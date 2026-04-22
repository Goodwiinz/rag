/**
 * Project Store - Zustand state management for Research Projects
 */

import { create } from 'zustand';
import axios from 'axios';
import { projectService } from '@/services/projectService';
import type {
  Project,
  ProjectCreate,
  ProjectUpdate,
  ProjectDocument,
  ProjectNote,
  ProjectNoteCreate,
  ProjectNoteUpdate,
  ProjectBibliography,
} from '@/services/projectService';

interface ProjectState {
  // State
  projects: Project[];
  currentProject: Project | null;
  projectDocuments: ProjectDocument[];
  projectNotes: ProjectNote[];
  bibliography: ProjectBibliography | null;
  loading: boolean;
  documentsLoading: boolean;
  notesLoading: boolean;
  error: string | null;
  total: number;

  // Project Actions
  fetchProjects: (
    params?: {
      workspace_id?: string;
      skip?: number;
      limit?: number;
      search?: string;
      project_status?: 'active' | 'paused' | 'completed' | 'archived';
      project_type?: 'research' | 'literature_review' | 'thesis' | 'paper';
      tag?: string;
    },
    options?: { signal?: AbortSignal }
  ) => Promise<void>;
  fetchProject: (projectId: string) => Promise<void>;
  createProject: (data: ProjectCreate) => Promise<Project>;
  updateProject: (projectId: string, data: ProjectUpdate) => Promise<void>;
  deleteProject: (projectId: string) => Promise<void>;
  setCurrentProject: (project: Project | null) => void;

  // Document Actions
  fetchProjectDocuments: (projectId: string) => Promise<void>;
  addDocument: (projectId: string, documentId: string) => Promise<void>;
  removeDocument: (projectId: string, documentId: string) => Promise<void>;

  // Note Actions
  fetchProjectNotes: (projectId: string, pinnedOnly?: boolean) => Promise<void>;
  createNote: (projectId: string, data: ProjectNoteCreate) => Promise<ProjectNote>;
  updateNote: (projectId: string, noteId: string, data: ProjectNoteUpdate) => Promise<void>;
  deleteNote: (projectId: string, noteId: string) => Promise<void>;
  toggleNotePin: (projectId: string, noteId: string) => Promise<void>;

  // Bibliography Actions
  fetchBibliography: (projectId: string, format?: 'bibtex' | 'ieee' | 'apa' | 'mla') => Promise<void>;
  downloadBibliography: (projectId: string, format?: 'bibtex' | 'ieee' | 'apa' | 'mla') => Promise<void>;

  // Utility
  clearError: () => void;
  reset: () => void;
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  // Initial state
  projects: [],
  currentProject: null,
  projectDocuments: [],
  projectNotes: [],
  bibliography: null,
  loading: false,
  documentsLoading: false,
  notesLoading: false,
  error: null,
  total: 0,

  // =========================================================================
  // Project Actions
  // =========================================================================

  fetchProjects: async (params, options) => {
    set({ loading: true, error: null });
    try {
      const response = await projectService.listProjects(params, options);
      set({
        projects: response.projects,
        total: response.total,
        loading: false,
      });
    } catch (error: any) {
      // Aborted requests (e.g., workspace switched or component unmounted
      // before the previous fetch settled) must still clear `loading` — the
      // common case is that a superseding fetch has already set it back to
      // true, but on unmount nothing replaces us and the spinner would
      // otherwise stick in the global store until the next visit.
      if (axios.isCancel(error) || error?.name === 'CanceledError') {
        set({ loading: false });
        return;
      }
      console.error('[ProjectStore] Failed to fetch projects:', error);
      set({
        error: error?.message || 'Failed to fetch projects',
        loading: false,
      });
    }
  },

  fetchProject: async (projectId) => {
    set({ loading: true, error: null });
    try {
      const project = await projectService.getProject(projectId);
      set({ currentProject: project, loading: false });
    } catch (error: any) {
      console.error('[ProjectStore] Failed to fetch project:', error);
      set({
        error: error?.message || 'Failed to fetch project',
        loading: false,
      });
    }
  },

  createProject: async (data) => {
    set({ loading: true, error: null });
    try {
      const project = await projectService.createProject(data);
      set((state) => ({
        projects: [project, ...state.projects],
        total: state.total + 1,
        loading: false,
      }));
      return project;
    } catch (error: any) {
      console.error('[ProjectStore] Failed to create project:', error);
      set({
        error: error?.message || 'Failed to create project',
        loading: false,
      });
      throw error;
    }
  },

  updateProject: async (projectId, data) => {
    set({ loading: true, error: null });
    try {
      const updated = await projectService.updateProject(projectId, data);
      set((state) => ({
        projects: state.projects.map((p) => (p.id === projectId ? updated : p)),
        currentProject: state.currentProject?.id === projectId ? updated : state.currentProject,
        loading: false,
      }));
    } catch (error: any) {
      console.error('[ProjectStore] Failed to update project:', error);
      set({
        error: error?.message || 'Failed to update project',
        loading: false,
      });
      throw error;
    }
  },

  deleteProject: async (projectId) => {
    set({ loading: true, error: null });
    try {
      await projectService.deleteProject(projectId);
      set((state) => ({
        projects: state.projects.filter((p) => p.id !== projectId),
        currentProject: state.currentProject?.id === projectId ? null : state.currentProject,
        total: state.total - 1,
        loading: false,
      }));
    } catch (error: any) {
      console.error('[ProjectStore] Failed to delete project:', error);
      set({
        error: error?.message || 'Failed to delete project',
        loading: false,
      });
      throw error;
    }
  },

  setCurrentProject: (project) => {
    set({ currentProject: project });
  },

  // =========================================================================
  // Document Actions
  // =========================================================================

  fetchProjectDocuments: async (projectId) => {
    set({ documentsLoading: true, error: null });
    try {
      const response = await projectService.listProjectDocuments(projectId);
      set({
        projectDocuments: response.documents,
        documentsLoading: false,
      });
    } catch (error: any) {
      console.error('[ProjectStore] Failed to fetch documents:', error);
      set({
        error: error?.message || 'Failed to fetch documents',
        documentsLoading: false,
      });
    }
  },

  addDocument: async (projectId, documentId) => {
    set({ documentsLoading: true, error: null });
    try {
      const doc = await projectService.addDocumentToProject(projectId, documentId);
      set((state) => ({
        projectDocuments: [...state.projectDocuments, doc],
        documentsLoading: false,
      }));
    } catch (error: any) {
      console.error('[ProjectStore] Failed to add document:', error);
      set({
        error: error?.message || 'Failed to add document',
        documentsLoading: false,
      });
      throw error;
    }
  },

  removeDocument: async (projectId, documentId) => {
    set({ documentsLoading: true, error: null });
    try {
      await projectService.removeDocumentFromProject(projectId, documentId);
      set((state) => ({
        projectDocuments: state.projectDocuments.filter((d) => d.document_id !== documentId),
        documentsLoading: false,
      }));
    } catch (error: any) {
      console.error('[ProjectStore] Failed to remove document:', error);
      set({
        error: error?.message || 'Failed to remove document',
        documentsLoading: false,
      });
      throw error;
    }
  },

  // =========================================================================
  // Note Actions
  // =========================================================================

  fetchProjectNotes: async (projectId, pinnedOnly = false) => {
    set({ notesLoading: true, error: null });
    try {
      const response = await projectService.listProjectNotes(projectId, {
        pinned_only: pinnedOnly,
      });
      set({
        projectNotes: response.notes,
        notesLoading: false,
      });
    } catch (error: any) {
      console.error('[ProjectStore] Failed to fetch notes:', error);
      set({
        error: error?.message || 'Failed to fetch notes',
        notesLoading: false,
      });
    }
  },

  createNote: async (projectId, data) => {
    set({ notesLoading: true, error: null });
    try {
      const note = await projectService.createNote(projectId, data);
      set((state) => ({
        projectNotes: [note, ...state.projectNotes],
        notesLoading: false,
      }));
      return note;
    } catch (error: any) {
      console.error('[ProjectStore] Failed to create note:', error);
      set({
        error: error?.message || 'Failed to create note',
        notesLoading: false,
      });
      throw error;
    }
  },

  updateNote: async (projectId, noteId, data) => {
    set({ notesLoading: true, error: null });
    try {
      const updated = await projectService.updateNote(projectId, noteId, data);
      set((state) => ({
        projectNotes: state.projectNotes.map((n) => (n.id === noteId ? updated : n)),
        notesLoading: false,
      }));
    } catch (error: any) {
      console.error('[ProjectStore] Failed to update note:', error);
      set({
        error: error?.message || 'Failed to update note',
        notesLoading: false,
      });
      throw error;
    }
  },

  deleteNote: async (projectId, noteId) => {
    set({ notesLoading: true, error: null });
    try {
      await projectService.deleteNote(projectId, noteId);
      set((state) => ({
        projectNotes: state.projectNotes.filter((n) => n.id !== noteId),
        notesLoading: false,
      }));
    } catch (error: any) {
      console.error('[ProjectStore] Failed to delete note:', error);
      set({
        error: error?.message || 'Failed to delete note',
        notesLoading: false,
      });
      throw error;
    }
  },

  toggleNotePin: async (projectId, noteId) => {
    try {
      const updated = await projectService.toggleNotePin(projectId, noteId);
      set((state) => ({
        projectNotes: state.projectNotes.map((n) => (n.id === noteId ? updated : n)),
      }));
    } catch (error: any) {
      console.error('[ProjectStore] Failed to toggle pin:', error);
      set({
        error: error?.message || 'Failed to toggle pin',
      });
      throw error;
    }
  },

  // =========================================================================
  // Bibliography Actions
  // =========================================================================

  fetchBibliography: async (projectId, format = 'bibtex') => {
    set({ loading: true, error: null });
    try {
      const bibliography = await projectService.getProjectBibliography(projectId, format);
      set({ bibliography, loading: false });
    } catch (error: any) {
      console.error('[ProjectStore] Failed to fetch bibliography:', error);
      set({
        error: error?.message || 'Failed to fetch bibliography',
        loading: false,
      });
    }
  },

  downloadBibliography: async (projectId, format = 'bibtex') => {
    try {
      await projectService.downloadBibliography(projectId, format);
    } catch (error: any) {
      console.error('[ProjectStore] Failed to download bibliography:', error);
      set({
        error: error?.message || 'Failed to download bibliography',
      });
      throw error;
    }
  },

  // =========================================================================
  // Utility
  // =========================================================================

  clearError: () => {
    set({ error: null });
  },

  reset: () => {
    set({
      projects: [],
      currentProject: null,
      projectDocuments: [],
      projectNotes: [],
      bibliography: null,
      loading: false,
      documentsLoading: false,
      notesLoading: false,
      error: null,
      total: 0,
    });
  },
}));

export default useProjectStore;
