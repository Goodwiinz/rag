/**
 * R4-L19: an SSE stream that emits a confirmation frame and then dies must
 * NOT fall back to the durable Trigger.dev run — the backend has already
 * parked the turn awaiting confirmation, and re-running it from scratch
 * would double-execute whatever the confirmed tool does.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAgentChatStore } from '@/store/agentChatStore';
import type { AgentStreamCallbacks } from '@/services/agentChatService';

const serviceMocks = vi.hoisted(() => ({
  listThreads: vi.fn(async () => ({ threads: [] })),
  getThreadMessages: vi.fn(async () => ({ messages: [] })),
  streamMessage: vi.fn(async () => {}),
  startDurableRun: vi.fn(async () => ({ runId: 'run-stub' })),
  getDurableRunStatus: vi.fn(async () => ({ status: 'PENDING' })),
  streamConfirm: vi.fn(async () => {}),
  confirmAction: vi.fn(async () => {}),
  completeDurableConfirmation: vi.fn(async () => {}),
  pollJob: vi.fn(async () => ({ status: 'pending' })),
}));

vi.mock('@/services/agentChatService', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('@/services/agentChatService')>();
  return {
    isTerminalJobStatus: actual.isTerminalJobStatus,
    agentChatService: serviceMocks,
  };
});

describe('agentChatStore confirm-parked SSE death (R4-L19)', () => {
  beforeEach(() => {
    useAgentChatStore.getState().reset();
    vi.clearAllMocks();
    serviceMocks.getThreadMessages.mockResolvedValue({ messages: [] });
  });

  it('does not fall back to the durable run once a confirmation frame was seen', async () => {
    serviceMocks.streamMessage.mockImplementation((async (
      _req: unknown,
      callbacks: AgentStreamCallbacks
    ) => {
      callbacks.onConfirmation?.('thread-A', {
        message: 'Confirm?',
        tools: [{ name: 'ingest_arxiv', args: {} }],
      });
      throw new Error('socket hang up');
    }) as never);

    useAgentChatStore.getState().setInputValue('hello');
    await useAgentChatStore.getState().sendMessage();

    expect(serviceMocks.startDurableRun).not.toHaveBeenCalled();

    const assistants = useAgentChatStore
      .getState()
      .messages.filter((m) => m.role === 'assistant');
    expect(assistants).toHaveLength(1);
    expect(assistants[0].isStreaming).toBe(false);
    expect(assistants[0].content).toMatch(/confirmation/i);
    expect(useAgentChatStore.getState().isStreaming).toBe(false);
  });

  it('still falls back to the durable run when no confirmation frame was seen', async () => {
    serviceMocks.streamMessage.mockImplementation((async () => {
      throw new Error('socket hang up');
    }) as never);
    serviceMocks.getDurableRunStatus.mockResolvedValue({
      status: 'COMPLETED',
      output: { status: 'done' },
    });

    useAgentChatStore.getState().setInputValue('hello');
    vi.useFakeTimers();
    try {
      const send = useAgentChatStore.getState().sendMessage();
      await vi.advanceTimersByTimeAsync(200 * 3000 + 1000);
      await send;
    } finally {
      vi.useRealTimers();
    }

    expect(serviceMocks.startDurableRun).toHaveBeenCalled();
  });
});
