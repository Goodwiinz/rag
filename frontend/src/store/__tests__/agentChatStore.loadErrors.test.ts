/**
 * Round-3 M14: a failed thread/message load logged to the console and left the
 * store in its empty state, so the UI rendered "no conversations" / the
 * greeting for data that exists on the server.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

const serviceMocks = vi.hoisted(() => ({
  listThreads: vi.fn(),
  getThreadMessages: vi.fn(),
  streamMessage: vi.fn(),
  startDurableRun: vi.fn(),
  streamConfirm: vi.fn(),
  confirmAction: vi.fn(),
  completeDurableConfirmation: vi.fn(),
  getDurableRunStatus: vi.fn(),
  pollJob: vi.fn(),
}));

vi.mock('@/services/agentChatService', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('@/services/agentChatService')>();
  return {
    isTerminalJobStatus: actual.isTerminalJobStatus,
    agentChatService: serviceMocks,
  };
});

import { useAgentChatStore } from '@/store/agentChatStore';

describe('agentChatStore load failures', () => {
  beforeEach(() => {
    useAgentChatStore.getState().reset();
    vi.clearAllMocks();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('records why the thread list could not load', async () => {
    serviceMocks.listThreads.mockRejectedValue(new Error('network down'));

    await useAgentChatStore.getState().loadThreads();

    expect(useAgentChatStore.getState().threadsError).toBe('network down');
    expect(useAgentChatStore.getState().isLoadingThreads).toBe(false);
  });

  it('drops the error when the user starts a new conversation', async () => {
    useAgentChatStore.setState({ activeThreadId: 'thread-A' });
    serviceMocks.getThreadMessages.mockRejectedValueOnce(new Error('boom'));
    await useAgentChatStore.getState().loadThreadMessages('thread-A');
    expect(useAgentChatStore.getState().messagesError).toBe('boom');

    useAgentChatStore.getState().newThread();

    // Otherwise the blank conversation renders "could not load", with no
    // active thread to retry against.
    expect(useAgentChatStore.getState().messagesError).toBeNull();
  });

  it('records why a thread could not load, and clears it on success', async () => {
    // The store discards results for a thread the user has navigated away
    // from, so this has to look like the thread is still active.
    useAgentChatStore.setState({ activeThreadId: 'thread-A' });
    serviceMocks.getThreadMessages.mockRejectedValueOnce(
      new Error('gateway timeout')
    );

    await useAgentChatStore.getState().loadThreadMessages('thread-A');
    expect(useAgentChatStore.getState().messagesError).toBe('gateway timeout');

    serviceMocks.getThreadMessages.mockResolvedValueOnce({ messages: [] });
    await useAgentChatStore.getState().loadThreadMessages('thread-A');
    expect(useAgentChatStore.getState().messagesError).toBeNull();
  });
});
