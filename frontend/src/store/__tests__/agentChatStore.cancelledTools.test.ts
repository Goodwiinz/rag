/**
 * R4-L20: a tool that was still running when the user hit Stop (or when a
 * confirm superseded a live turn) should read as cancelled/interrupted, not
 * failed — the tool didn't error, the generation was cut short.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAgentChatStore } from '@/store/agentChatStore';

vi.mock('@/services/agentChatService', () => ({
  agentChatService: {
    streamMessage: vi.fn(),
    streamConfirm: vi.fn(),
    listThreads: vi.fn().mockResolvedValue({ threads: [], total: 0 }),
    getThreadMessages: vi.fn().mockResolvedValue({ messages: [], total: 0 }),
  },
  isTerminalJobStatus: vi.fn().mockReturnValue(true),
}));

describe('agentChatStore interrupted tool status (R4-L20)', () => {
  beforeEach(() => {
    useAgentChatStore.getState().reset();
    vi.clearAllMocks();
  });

  it('marks a running tool cancelled (not failed) when the user hits Stop', () => {
    useAgentChatStore.setState({
      isStreaming: true,
      messages: [
        {
          id: 'a-1',
          role: 'assistant',
          content: '',
          timestamp: new Date(),
          isStreaming: true,
          toolExecutions: [
            {
              id: 'te-1',
              toolName: 'search_documents',
              toolDisplayName: 'Search Documents',
              args: {},
              status: 'running',
            },
          ],
        },
      ],
    });

    useAgentChatStore.getState().stopGeneration();

    const execs = useAgentChatStore.getState().messages[0].toolExecutions!;
    expect(execs[0].status).toBe('cancelled');
  });

  it('marks a running tool cancelled when confirmAction supersedes a live turn', async () => {
    useAgentChatStore.setState({
      activeThreadId: 'thread-A',
      messages: [
        {
          id: 'a-live',
          role: 'assistant',
          content: 'partial answer',
          timestamp: new Date(),
          isStreaming: true,
          toolExecutions: [
            {
              id: 'te-1',
              toolName: 'search_documents',
              toolDisplayName: 'Search Documents',
              args: {},
              status: 'running',
            },
          ],
        },
        {
          id: 'a-1',
          role: 'assistant',
          content: 'Waiting for your confirmation...',
          timestamp: new Date(),
        },
      ],
      pendingConfirmations: {
        'thread-A': {
          threadId: 'thread-A',
          assistantMessageId: 'a-1',
          jobId: 'thread-A',
          origin: 'sse',
          tools: [{ name: 'ingest_arxiv', args: {} }],
          message: 'Confirm?',
        },
      },
    });
    (
      useAgentChatStore.getState() as unknown as {
        _abortController: AbortController | null;
      }
    )._abortController = new AbortController();

    await useAgentChatStore.getState().confirmAction('thread-A', true);

    const liveMessage = useAgentChatStore
      .getState()
      .messages.find((m) => m.id === 'a-live');
    expect(liveMessage?.toolExecutions?.[0].status).toBe('cancelled');
  });
});
