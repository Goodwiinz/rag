/**
 * Chat Store Streaming Tests
 *
 * Tests for the streaming state and actions in chat-store.ts:
 * - Streaming state properties exist with correct defaults
 * - streamMessage action exists as a function
 * - stopStreaming action exists as a function
 * - stopStreaming resets streaming state
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, waitFor } from '@testing-library/react';
import { enableMapSet } from 'immer';

// Enable Immer MapSet plugin before store import
enableMapSet();

// Mock workspace service (required by store module)
vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    listWorkspaces: vi.fn(),
    createWorkspace: vi.fn(),
    updateWorkspace: vi.fn(),
    deleteWorkspace: vi.fn(),
    getOrCreateDefaultWorkspace: vi.fn(),
    listConversations: vi.fn(),
    createConversation: vi.fn(),
    updateConversation: vi.fn(),
    deleteConversation: vi.fn(),
    listThreads: vi.fn(),
    createThread: vi.fn(),
    updateThread: vi.fn(),
    deleteThread: vi.fn(),
    bulkResolveThreads: vi.fn(),
    bulkArchiveThreads: vi.fn(),
    bulkSummarizeThreads: vi.fn(),
    bulkDeleteThreads: vi.fn(),
    listMessages: vi.fn(),
    createMessage: vi.fn(),
    updateMessage: vi.fn(),
    deleteMessage: vi.fn(),
  },
}));

const { streamChatMessageMock } = vi.hoisted(() => ({
  streamChatMessageMock: vi.fn(),
}));

vi.mock('@/services/streamingService', () => ({
  streamChatMessage: streamChatMessageMock,
}));

// Must import after mocks are set up
import { useChatStore } from '@/store/chat-store';
// Namespace import: `activeAbortController` is a mutable `let` export — read
// it through the namespace so we always see the live binding.
import * as requestCoordinator from '@/store/chat/requestCoordinator';

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

  // Pins the single-stream-ownership fix (PR #1205 triage, pre-existing bug):
  // the old code overwrote the active controller without aborting the previous
  // stream, and the superseded stream's cleanup then cleared state belonging
  // to the newer stream. This test FAILS against the old behavior (the
  // un-aborted first stream hangs forever).
  describe('streamMessage single-stream ownership', () => {
    beforeEach(() => {
      streamChatMessageMock.mockReset();
    });

    // Yields one token, then hangs until the request signal aborts.
    const hangingStream = (
      signal: AbortSignal,
      token: string
    ): AsyncGenerator<{ type: string; data: { content: string } }> =>
      (async function* () {
        yield { type: 'token', data: { content: token } };
        await new Promise((_, reject) => {
          const abort = (): void =>
            reject(new DOMException('Aborted', 'AbortError'));
          if (signal.aborted) {
            abort();
            return;
          }
          signal.addEventListener('abort', abort);
        });
      })();

    it('aborts the superseded stream and its cleanup leaves the new stream untouched', async () => {
      const signals: AbortSignal[] = [];
      streamChatMessageMock.mockImplementation(
        (
          _threadId: string,
          content: string,
          _opts: { useRag: boolean },
          signal: AbortSignal
        ) => {
          signals.push(signal);
          return hangingStream(signal, content);
        }
      );
      useChatStore.setState({ currentThreadId: 't1' });

      let first!: Promise<void>;
      let second!: Promise<void>;
      await act(async () => {
        first = useChatStore.getState().streamMessage('one');
        await waitFor(() =>
          expect(useChatStore.getState().streamingContent).toBe('one')
        );
        second = useChatStore.getState().streamMessage('two');
        await waitFor(() =>
          expect(useChatStore.getState().streamingContent).toBe('two')
        );

        // Starting the second stream aborted the first one's request
        expect(signals).toHaveLength(2);
        expect(signals[0].aborted).toBe(true);
        expect(signals[1].aborted).toBe(false);

        // The superseded stream's cleanup ran (first resolves) but must not
        // clear state or the controller now owned by the second stream
        await first;
        expect(useChatStore.getState().isStreaming).toBe(true);
        expect(useChatStore.getState().streamingContent).toBe('two');
        expect(requestCoordinator.activeAbortController).not.toBeNull();

        // A user stop still cleans up the (current) second stream
        useChatStore.getState().stopStreaming();
        await second;
        expect(useChatStore.getState().isStreaming).toBe(false);
        expect(requestCoordinator.activeAbortController).toBeNull();
      });
    });
  });
});
