/**
 * Unit tests for Project-Chat Integration Service
 *
 * Tests API client calls with mocked responses
 */

import { projectChatService } from '../projectChatService';
import { apiClient } from '../apiClient';
import type {
  StartChatFromProjectRequest,
  StartChatFromProjectResponse,
  LinkThreadRequest,
  ProjectThread,
  ProjectThreadListResponse,
  SaveThreadToNoteRequest,
} from '@/types/project-chat';

// Mock the API client
jest.mock('../apiClient', () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
    delete: jest.fn(),
  },
}));

const mockApiClient = apiClient as jest.Mocked<typeof apiClient>;

// ============================================================================
// Test Data Factories
// ============================================================================

const createMockProjectThread = (overrides: Partial<ProjectThread> = {}): ProjectThread => ({
  id: 'pt-123',
  project_id: 'proj-456',
  thread_id: 'thread-789',
  thread_title: 'Test Discussion',
  conversation_id: 'conv-101',
  link_type: 'manual',
  linked_at: new Date().toISOString(),
  linked_by_id: 'user-001',
  context_note: 'Test context',
  message_count: 5,
  last_message_at: new Date().toISOString(),
  ...overrides,
});

const createMockStartResponse = (overrides: Partial<StartChatFromProjectResponse> = {}): StartChatFromProjectResponse => ({
  thread_id: 'thread-new-123',
  conversation_id: 'conv-new-456',
  project_thread_id: 'pt-new-789',
  document_scope: ['doc-1', 'doc-2'],
  ...overrides,
});

// ============================================================================
// Test Suite
// ============================================================================

describe('projectChatService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ==========================================================================
  // startChatFromProject
  // ==========================================================================

  describe('startChatFromProject', () => {
    const projectId = 'proj-123';
    const request: StartChatFromProjectRequest = {
      initial_message: 'Hello, let\'s discuss this research',
      thread_title: 'Research Discussion',
    };

    it('should call POST with correct endpoint and payload', async () => {
      const mockResponse = createMockStartResponse();
      mockApiClient.post.mockResolvedValue(mockResponse);

      await projectChatService.startChatFromProject(projectId, request);

      expect(mockApiClient.post).toHaveBeenCalledWith(
        `/projects/${projectId}/chat/start`,
        request
      );
    });

    it('should return start chat response on success', async () => {
      const mockResponse = createMockStartResponse();
      mockApiClient.post.mockResolvedValue(mockResponse);

      const result = await projectChatService.startChatFromProject(projectId, request);

      expect(result).toEqual(mockResponse);
      expect(result.thread_id).toBe('thread-new-123');
      expect(result.document_scope).toHaveLength(2);
    });

    it('should handle request with existing conversation_id', async () => {
      const requestWithConv: StartChatFromProjectRequest = {
        ...request,
        conversation_id: 'conv-existing-123',
      };
      const mockResponse = createMockStartResponse({
        conversation_id: 'conv-existing-123',
      });
      mockApiClient.post.mockResolvedValue(mockResponse);

      const result = await projectChatService.startChatFromProject(projectId, requestWithConv);

      expect(result.conversation_id).toBe('conv-existing-123');
    });

    it('should propagate API errors', async () => {
      const error = new Error('Network error');
      mockApiClient.post.mockRejectedValue(error);

      await expect(
        projectChatService.startChatFromProject(projectId, request)
      ).rejects.toThrow('Network error');
    });
  });

  // ==========================================================================
  // linkThreadToProject
  // ==========================================================================

  describe('linkThreadToProject', () => {
    const projectId = 'proj-123';
    const request: LinkThreadRequest = {
      thread_id: 'thread-to-link',
      context_note: 'Relevant to machine learning research',
    };

    it('should call POST with correct endpoint and payload', async () => {
      const mockResponse = createMockProjectThread();
      mockApiClient.post.mockResolvedValue(mockResponse);

      await projectChatService.linkThreadToProject(projectId, request);

      expect(mockApiClient.post).toHaveBeenCalledWith(
        `/projects/${projectId}/chat/link`,
        request
      );
    });

    it('should return project thread on success', async () => {
      const mockResponse = createMockProjectThread();
      mockApiClient.post.mockResolvedValue(mockResponse);

      const result = await projectChatService.linkThreadToProject(projectId, request);

      expect(result).toEqual(mockResponse);
      expect(result.link_type).toBe('manual');
    });

    it('should handle request without context note', async () => {
      const requestWithoutNote: LinkThreadRequest = {
        thread_id: 'thread-to-link',
      };
      const mockResponse = createMockProjectThread({ context_note: undefined });
      mockApiClient.post.mockResolvedValue(mockResponse);

      const result = await projectChatService.linkThreadToProject(projectId, requestWithoutNote);

      expect(result.context_note).toBeUndefined();
    });

    it('should propagate conflict errors (duplicate link)', async () => {
      const error = { status: 409, message: 'Thread already linked' };
      mockApiClient.post.mockRejectedValue(error);

      await expect(
        projectChatService.linkThreadToProject(projectId, request)
      ).rejects.toEqual(error);
    });
  });

  // ==========================================================================
  // listProjectThreads
  // ==========================================================================

  describe('listProjectThreads', () => {
    const projectId = 'proj-123';

    it('should call GET with correct endpoint', async () => {
      const mockResponse: ProjectThreadListResponse = {
        threads: [createMockProjectThread()],
        total: 1,
      };
      mockApiClient.get.mockResolvedValue(mockResponse);

      await projectChatService.listProjectThreads(projectId);

      expect(mockApiClient.get).toHaveBeenCalledWith(
        `/projects/${projectId}/chat/threads`
      );
    });

    it('should return list of threads on success', async () => {
      const mockResponse: ProjectThreadListResponse = {
        threads: [
          createMockProjectThread({ id: 'pt-1' }),
          createMockProjectThread({ id: 'pt-2' }),
        ],
        total: 2,
      };
      mockApiClient.get.mockResolvedValue(mockResponse);

      const result = await projectChatService.listProjectThreads(projectId);

      expect(result.threads).toHaveLength(2);
      expect(result.total).toBe(2);
    });

    it('should return empty list when no threads linked', async () => {
      const mockResponse: ProjectThreadListResponse = {
        threads: [],
        total: 0,
      };
      mockApiClient.get.mockResolvedValue(mockResponse);

      const result = await projectChatService.listProjectThreads(projectId);

      expect(result.threads).toEqual([]);
      expect(result.total).toBe(0);
    });

    it('should propagate 404 errors', async () => {
      const error = { status: 404, message: 'Project not found' };
      mockApiClient.get.mockRejectedValue(error);

      await expect(
        projectChatService.listProjectThreads(projectId)
      ).rejects.toEqual(error);
    });
  });

  // ==========================================================================
  // unlinkThreadFromProject
  // ==========================================================================

  describe('unlinkThreadFromProject', () => {
    const projectId = 'proj-123';
    const threadId = 'thread-456';

    it('should call DELETE with correct endpoint', async () => {
      mockApiClient.delete.mockResolvedValue(undefined);

      await projectChatService.unlinkThreadFromProject(projectId, threadId);

      expect(mockApiClient.delete).toHaveBeenCalledWith(
        `/projects/${projectId}/chat/threads/${threadId}`
      );
    });

    it('should return void on success', async () => {
      mockApiClient.delete.mockResolvedValue(undefined);

      const result = await projectChatService.unlinkThreadFromProject(projectId, threadId);

      expect(result).toBeUndefined();
    });

    it('should propagate 404 errors (link not found)', async () => {
      const error = { status: 404, message: 'Thread link not found' };
      mockApiClient.delete.mockRejectedValue(error);

      await expect(
        projectChatService.unlinkThreadFromProject(projectId, threadId)
      ).rejects.toEqual(error);
    });
  });

  // ==========================================================================
  // saveThreadToNote
  // ==========================================================================

  describe('saveThreadToNote', () => {
    const projectId = 'proj-123';
    const request: SaveThreadToNoteRequest = {
      thread_id: 'thread-789',
      note_title: 'Research Discussion Summary',
      include_citations: true,
    };

    it('should call POST with correct endpoint and payload', async () => {
      const mockResponse = {
        id: 'note-123',
        project_id: projectId,
        title: 'Research Discussion Summary',
        content: '# Thread content',
        created_at: new Date().toISOString(),
      };
      mockApiClient.post.mockResolvedValue(mockResponse);

      await projectChatService.saveThreadToNote(projectId, request);

      expect(mockApiClient.post).toHaveBeenCalledWith(
        `/projects/${projectId}/chat/save-to-note`,
        request
      );
    });

    it('should return note response on success', async () => {
      const mockResponse = {
        id: 'note-123',
        project_id: projectId,
        title: 'Research Discussion Summary',
        content: '# Thread content\n\n## User\n\nHello',
        tags: ['chat-thread'],
        created_at: new Date().toISOString(),
      };
      mockApiClient.post.mockResolvedValue(mockResponse);

      const result = await projectChatService.saveThreadToNote(projectId, request);

      expect(result.title).toBe('Research Discussion Summary');
      expect(result.tags).toContain('chat-thread');
    });

    it('should handle request without citations', async () => {
      const requestNoCitations: SaveThreadToNoteRequest = {
        ...request,
        include_citations: false,
      };
      const mockResponse = {
        id: 'note-123',
        title: 'Note without citations',
        content: '# Simple content',
      };
      mockApiClient.post.mockResolvedValue(mockResponse);

      await projectChatService.saveThreadToNote(projectId, requestNoCitations);

      expect(mockApiClient.post).toHaveBeenCalledWith(
        `/projects/${projectId}/chat/save-to-note`,
        requestNoCitations
      );
    });

    it('should propagate errors', async () => {
      const error = new Error('Failed to save note');
      mockApiClient.post.mockRejectedValue(error);

      await expect(
        projectChatService.saveThreadToNote(projectId, request)
      ).rejects.toThrow('Failed to save note');
    });
  });

  // ==========================================================================
  // Edge Cases
  // ==========================================================================

  describe('edge cases', () => {
    it('should handle special characters in project ID', async () => {
      const specialProjectId = 'proj-123-abc';
      mockApiClient.get.mockResolvedValue({ threads: [], total: 0 });

      await projectChatService.listProjectThreads(specialProjectId);

      expect(mockApiClient.get).toHaveBeenCalledWith(
        `/projects/${specialProjectId}/chat/threads`
      );
    });

    it('should handle long thread titles', async () => {
      const mockThread = createMockProjectThread({
        thread_title: 'A'.repeat(500),
      });
      const mockResponse: ProjectThreadListResponse = {
        threads: [mockThread],
        total: 1,
      };
      mockApiClient.get.mockResolvedValue(mockResponse);

      const result = await projectChatService.listProjectThreads('proj-123');

      expect(result.threads[0].thread_title).toHaveLength(500);
    });

    it('should handle empty document scope', async () => {
      const mockResponse = createMockStartResponse({
        document_scope: [],
      });
      mockApiClient.post.mockResolvedValue(mockResponse);

      const result = await projectChatService.startChatFromProject(
        'proj-123',
        { initial_message: 'Test' }
      );

      expect(result.document_scope).toEqual([]);
    });
  });
});
