/**
 * Chat Store Streaming Tests
 *
 * Tests for the streaming state and actions in chat-store.ts:
 * - Streaming state properties exist with correct defaults
 * - streamMessage action exists as a function
 * - stopStreaming action exists as a function
 * - stopStreaming resets streaming state
 */

import { act } from '@testing-library/react';
import { enableMapSet } from 'immer';

// Enable Immer MapSet plugin before store import
enableMapSet();

// Mock workspace service (required by store module)
jest.mock('@/services/workspaceService', () => ({
  workspaceService: {
    listWorkspaces: jest.fn(),
    createWorkspace: jest.fn(),
    updateWorkspace: jest.fn(),
    deleteWorkspace: jest.fn(),
    getOrCreateDefaultWorkspace: jest.fn(),
    listConversations: jest.fn(),
    createConversation: jest.fn(),
    updateConversation: jest.fn(),
    deleteConversation: jest.fn(),
    listThreads: jest.fn(),
    createThread: jest.fn(),
    updateThread: jest.fn(),
    deleteThread: jest.fn(),
    bulkResolveThreads: jest.fn(),
    bulkArchiveThreads: jest.fn(),
    bulkSummarizeThreads: jest.fn(),
    bulkDeleteThreads: jest.fn(),
    listMessages: jest.fn(),
    createMessage: jest.fn(),
    updateMessage: jest.fn(),
    deleteMessage: jest.fn(),
  },
}));

// Must import after mocks are set up
import { useChatStore } from '@/store/chat-store';

describe('Chat Store Streaming State and Actions', () => {
  beforeEach(() => {
    // Reset store to initial state before each test
    act(() => {
      useChatStore.getState().reset();
    });
  });

  describe('initial streaming state', () => {
    it('should have isStreaming set to false', () => {
      expect(useChatStore.getState().isStreaming).toBe(false);
    });

    it('should have streamingContent set to empty string', () => {
      expect(useChatStore.getState().streamingContent).toBe('');
    });

    it('should have streamingMessageId set to null', () => {
      expect(useChatStore.getState().streamingMessageId).toBeNull();
    });

    it('should have streamingCitations set to empty array', () => {
      expect(useChatStore.getState().streamingCitations).toEqual([]);
    });

    it('should not have abortController in state (moved to module level)', () => {
      expect('abortController' in useChatStore.getState()).toBe(false);
    });
  });

  describe('streamMessage action', () => {
    it('should exist as a function', () => {
      expect(typeof useChatStore.getState().streamMessage).toBe('function');
    });
  });

  describe('stopStreaming action', () => {
    it('should exist as a function', () => {
      expect(typeof useChatStore.getState().stopStreaming).toBe('function');
    });

    it('should reset all streaming state', () => {
      // Manually set streaming state to non-default values
      act(() => {
        useChatStore.setState({
          isStreaming: true,
          streamingContent: 'partial response...',
          streamingMessageId: 'msg-123',
          streamingCitations: [{ source: 'test' }],
          abortController: new AbortController(),
        });
      });

      // Verify state was set
      expect(useChatStore.getState().isStreaming).toBe(true);
      expect(useChatStore.getState().streamingContent).toBe(
        'partial response...'
      );
      expect(useChatStore.getState().streamingMessageId).toBe('msg-123');
      expect(useChatStore.getState().streamingCitations).toHaveLength(1);
      // Call stopStreaming
      act(() => {
        useChatStore.getState().stopStreaming();
      });

      // Verify streaming state is reset
      expect(useChatStore.getState().isStreaming).toBe(false);
      expect(useChatStore.getState().streamingContent).toBe('');
      expect(useChatStore.getState().streamingMessageId).toBeNull();
      expect(useChatStore.getState().streamingCitations).toEqual([]);
    });

    it('should handle stopStreaming when not streaming', () => {
      act(() => {
        useChatStore.setState({
          isStreaming: true,
          streamingContent: 'some content',
        });
      });

      // Should not throw
      act(() => {
        useChatStore.getState().stopStreaming();
      });

      expect(useChatStore.getState().isStreaming).toBe(false);
      expect(useChatStore.getState().streamingContent).toBe('');
    });
  });
});
