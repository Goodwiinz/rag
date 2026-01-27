/**
 * Project-Chat Integration Service
 * Handles API calls for linking research projects to chat threads
 *
 * Backend API: /api/v1/projects/{id}/chat/*
 */

import { apiClient } from './apiClient';
import type {
  StartChatFromProjectRequest,
  StartChatFromProjectResponse,
  LinkThreadRequest,
  ProjectThread,
  ProjectThreadListResponse,
  SaveThreadToNoteRequest,
} from '@/types/project-chat';
import type { NoteResponse } from '@/types/research';

// Note: apiClient already has baseURL of http://localhost:8000/api/v1
// So we only need the path after /api/v1
const BASE_PATH = '/projects';

/**
 * Project-Chat Integration Service
 * Object-based service for all project-chat operations
 */
export const projectChatService = {
  /**
   * Start a new chat thread from a project with document context
   * POST /api/v1/projects/{id}/chat/start
   *
   * @param projectId - Project UUID
   * @param request - Chat start request with initial message
   * @returns Thread details with document scope
   */
  async startChatFromProject(
    projectId: string,
    request: StartChatFromProjectRequest
  ): Promise<StartChatFromProjectResponse> {
    return apiClient.post<StartChatFromProjectResponse>(
      `${BASE_PATH}/${projectId}/chat/start`,
      request
    );
  },

  /**
   * Link an existing thread to a project
   * POST /api/v1/projects/{id}/chat/link
   *
   * @param projectId - Project UUID
   * @param request - Thread link request with thread_id
   * @returns Created project-thread link
   */
  async linkThreadToProject(
    projectId: string,
    request: LinkThreadRequest
  ): Promise<ProjectThread> {
    return apiClient.post<ProjectThread>(
      `${BASE_PATH}/${projectId}/chat/link`,
      request
    );
  },

  /**
   * List all threads linked to a project
   * GET /api/v1/projects/{id}/chat/threads
   *
   * @param projectId - Project UUID
   * @returns List of linked threads with metadata
   */
  async listProjectThreads(projectId: string): Promise<ProjectThreadListResponse> {
    return apiClient.get<ProjectThreadListResponse>(
      `${BASE_PATH}/${projectId}/chat/threads`
    );
  },

  /**
   * Unlink a thread from a project
   * DELETE /api/v1/projects/{id}/chat/threads/{thread_id}
   *
   * @param projectId - Project UUID
   * @param threadId - Thread UUID to unlink
   */
  async unlinkThreadFromProject(projectId: string, threadId: string): Promise<void> {
    await apiClient.delete(`${BASE_PATH}/${projectId}/chat/threads/${threadId}`);
  },

  /**
   * Save thread content to a project note
   * POST /api/v1/projects/{id}/chat/save-to-note
   *
   * @param projectId - Project UUID
   * @param request - Save to note request with thread_id and note_title
   * @returns Created note
   */
  async saveThreadToNote(
    projectId: string,
    request: SaveThreadToNoteRequest
  ): Promise<NoteResponse> {
    return apiClient.post<NoteResponse>(
      `${BASE_PATH}/${projectId}/chat/save-to-note`,
      request
    );
  },
};

export default projectChatService;
