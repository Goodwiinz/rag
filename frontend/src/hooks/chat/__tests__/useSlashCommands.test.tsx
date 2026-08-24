import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { ChatConversation } from '@/hooks/chat/chatTypes';
import {
  useSlashCommands,
  type UseSlashCommandsReturn,
} from '@/hooks/chat/useSlashCommands';

const mockRouterPush = vi.fn();
const mockRouterReplace = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockRouterPush, replace: mockRouterReplace }),
}));

const createMemoryMock = vi.fn();
const listMemoriesMock = vi.fn();
const deleteMemoryMock = vi.fn();
vi.mock('@/services/projectService', () => ({
  projectService: {
    createMemory: (...args: unknown[]) => createMemoryMock(...args),
    listMemories: (...args: unknown[]) => listMemoriesMock(...args),
    deleteMemory: (...args: unknown[]) => deleteMemoryMock(...args),
  },
}));

vi.mock('@/services/documentService', () => ({
  documentService: { getDocuments: vi.fn().mockResolvedValue({ documents: [] }) },
}));

const linkThreadToProjectMock = vi.fn();
vi.mock('@/store/projectChatStore', () => ({
  useProjectChatStore: {
    getState: () => ({
      linkThreadToProject: (...args: unknown[]) =>
        linkThreadToProjectMock(...args),
      errors: {},
    }),
  },
}));

function makeConversation(
  overrides: Partial<ChatConversation> = {}
): ChatConversation {
  return {
    id: 'thread-1',
    title: 'Thread 1',
    messages: [],
    createdAt: 1,
    updatedAt: 1,
    threadId: 'thread-1',
    conversationId: 'conv-1',
    ...overrides,
  };
}

function setup(overrides: Record<string, unknown> = {}): {
  result: { current: UseSlashCommandsReturn };
  setInput: ReturnType<typeof vi.fn>;
  handleSubmit: ReturnType<typeof vi.fn>;
  submit: ReturnType<typeof vi.fn>;
  retryLast: ReturnType<typeof vi.fn>;
  setCurrentThread: ReturnType<typeof vi.fn>;
  params: Record<string, unknown>;
} {
  const setInput = vi.fn();
  const handleSubmit = vi.fn();
  const submit = vi.fn();
  const retryLast = vi.fn();
  const setCurrentThread = vi.fn();
  const chatInputRef = { current: null } as React.RefObject<HTMLTextAreaElement>;
  const params = {
    input: '',
    setInput,
    handleSubmit,
    submit,
    retryLast,
    conversations: [makeConversation()],
    activeThreadId: 'thread-1',
    setCurrentThread,
    chatInputRef,
    ...overrides,
  };
  const { result } = renderHook(() => useSlashCommands(params));
  return { result, setInput, handleSubmit, submit, retryLast, setCurrentThread, params };
}

describe('useSlashCommands', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('/new starts a fresh chat', () => {
    const { result, setCurrentThread } = setup();

    act(() => {
      result.current.handleSlashCommand('new');
    });

    expect(setCurrentThread).toHaveBeenCalledWith(null);
    expect(mockRouterPush).toHaveBeenCalledWith('/chat?new=1');
  });

  it('/clear resets command output and the composer input', () => {
    const { result, setInput } = setup();

    act(() => {
      result.current.handleSlashCommand('help');
    });
    expect(result.current.commandOutputs).toHaveLength(1);

    act(() => {
      result.current.handleSlashCommand('clear');
    });

    expect(result.current.commandOutputs).toHaveLength(0);
    expect(setInput).toHaveBeenCalledWith('');
  });

  it('/threads lists conversations and an item action opens the thread', () => {
    const { result, setCurrentThread } = setup();

    act(() => {
      result.current.handleSlashCommand('threads');
    });

    expect(result.current.commandOutputs[0].items).toEqual([
      expect.objectContaining({ key: 'thread-1', label: 'Thread 1' }),
    ]);

    act(() => {
      result.current.handleCommandItemAction({ type: 'open-thread', id: 'thread-1' });
    });

    expect(setCurrentThread).toHaveBeenCalledWith('thread-1');
    expect(mockRouterPush).toHaveBeenCalledWith('/chat?thread=thread-1');
  });

  it('binds the chat to a project via the set-project command action', async () => {
    linkThreadToProjectMock.mockResolvedValue({ thread_id: 'thread-1' });
    const { result } = setup();

    await act(async () => {
      result.current.handleCommandItemAction({
        type: 'set-project',
        id: 'proj-1',
        name: 'My Project',
      });
    });

    expect(mockRouterReplace).toHaveBeenCalledTimes(1);
    const url = mockRouterReplace.mock.calls[0][0] as string;
    expect(url).toContain('projectId=proj-1');
    expect(result.current.commandOutputs[0].lines).toEqual([
      'Project context set: My Project',
    ]);
    // The URL param is ignored once the thread row is loaded, so the binding
    // has to be persisted on the thread itself.
    expect(linkThreadToProjectMock).toHaveBeenCalledWith('proj-1', {
      thread_id: 'thread-1',
    });
  });

  it('reports a failed project attach instead of claiming success', async () => {
    linkThreadToProjectMock.mockResolvedValue(null);
    const { result } = setup();

    await act(async () => {
      result.current.handleCommandItemAction({
        type: 'set-project',
        id: 'proj-1',
        name: 'My Project',
      });
    });

    expect(result.current.commandOutputs[0].lines?.[0]).toBe(
      'Could not attach this chat to My Project.'
    );
  });

  it('skips the thread attach when no thread exists yet (new chat)', async () => {
    linkThreadToProjectMock.mockResolvedValue({ thread_id: 'thread-1' });
    const { result } = setup({ activeThreadId: null });

    await act(async () => {
      result.current.handleCommandItemAction({
        type: 'set-project',
        id: 'proj-1',
        name: 'My Project',
      });
    });

    expect(linkThreadToProjectMock).not.toHaveBeenCalled();
    expect(result.current.commandOutputs[0].lines).toEqual([
      'Project context set: My Project',
    ]);
  });

  it('/retry dispatches to the injected retryLast (useChatComposerActions)', () => {
    const { result, retryLast } = setup();

    act(() => {
      result.current.handleSlashCommand('retry');
    });

    expect(retryLast).toHaveBeenCalledTimes(1);
  });

  it('submitMessage sends a normal message straight through and clears output', () => {
    const { result, submit } = setup({ input: 'hello there' });

    act(() => {
      result.current.handleSlashCommand('help'); // seed some output first
    });
    act(() => {
      result.current.submitMessage();
    });

    expect(submit).toHaveBeenCalledTimes(1);
    expect(result.current.commandOutputs).toHaveLength(0);
  });

  it('submitMessage intercepts /remember instead of sending to the agent', () => {
    const { result, setInput, submit } = setup({
      input: '/remember always cite sources',
    });

    act(() => {
      result.current.submitMessage();
    });

    expect(submit).not.toHaveBeenCalled();
    expect(setInput).toHaveBeenCalledWith('');
  });
});
