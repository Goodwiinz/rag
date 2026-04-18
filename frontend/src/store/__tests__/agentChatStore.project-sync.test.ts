jest.mock('@/services/agentChatService', () => ({
  agentChatService: {
    streamMessage: jest.fn(),
    startJob: jest.fn(),
    pollJob: jest.fn(),
    confirmAction: jest.fn(),
    listThreads: jest.fn().mockResolvedValue({ threads: [], total: 0 }),
    getThreadMessages: jest.fn().mockResolvedValue({
      messages: [],
      total: 0,
    }),
  },
}));

import { act } from '@testing-library/react';
import { useAgentChatStore } from '@/store/agentChatStore';
import { agentChatService } from '@/services/agentChatService';

const mockAgentChatService = jest.mocked(agentChatService);

describe('agentChatStore project sync', () => {
  beforeEach(() => {
    useAgentChatStore.getState().reset();
    jest.clearAllMocks();
    mockAgentChatService.listThreads.mockResolvedValue({ threads: [], total: 0 });
    mockAgentChatService.getThreadMessages.mockResolvedValue({
      messages: [],
      total: 0,
    });
  });

  it('increments projectDataVersion for create_project_note tool executions in SSE mode', async () => {
    mockAgentChatService.streamMessage.mockImplementation(async (_request, callbacks) => {
      callbacks.onToolStart?.('create_project_note', {});
      callbacks.onToolEnd?.('create_project_note', '{"ok":true}');
      callbacks.onDone?.();
    });

    await act(async () => {
      useAgentChatStore.getState().setInputValue('create a note');
      await useAgentChatStore.getState().sendMessage();
    });

    expect(useAgentChatStore.getState().projectDataVersion).toBe(1);
  });

  it('increments projectDataVersion only once for a single mutating SSE tool execution', async () => {
    mockAgentChatService.streamMessage.mockImplementation(async (_request, callbacks) => {
      callbacks.onToolStart?.('add_document_to_project', {});
      callbacks.onToolEnd?.('add_document_to_project', '{"ok":true}');
      callbacks.onDone?.();
    });

    await act(async () => {
      useAgentChatStore.getState().setInputValue('add the paper');
      await useAgentChatStore.getState().sendMessage();
    });

    expect(useAgentChatStore.getState().projectDataVersion).toBe(1);
  });
});
