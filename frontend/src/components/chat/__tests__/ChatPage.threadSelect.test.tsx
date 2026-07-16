import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ChatPage from '../../../../app/(dashboard)/chat/page';

const mockUseChatSession = vi.fn();

vi.mock('@/components/chat', () => ({
  ChatInput: () => <div data-testid="chat-input" />,
  CitationPanel: () => <div data-testid="citation-panel" />,
  WelcomeState: () => <div data-testid="welcome-state" />,
}));

vi.mock('@/components/chat/ChatDialogs', () => ({
  ChatDialogs: () => <div data-testid="chat-dialogs" />,
}));

vi.mock('@/components/chat/ChatHeader', () => ({
  ChatHeader: () => <div data-testid="chat-header" />,
}));

vi.mock('@/components/chat/ChatMessageList', () => ({
  ChatMessageList: (props: {
    onCommandItemAction?: (action: { type: 'open-thread'; id: string }) => void;
    onLoadOlder?: () => void;
    hasMore?: boolean;
    isLoadingOlder?: boolean;
    messages?: Array<{ role: string; content: string }>;
  }) => (
    <div>
      <button
        type="button"
        data-testid="chat-command-open-thread"
        onClick={() =>
          props.onCommandItemAction?.({ type: 'open-thread', id: 'thread-2' })
        }
      >
        Open command thread
      </button>
      <button
        type="button"
        data-testid="load-older"
        onClick={() => props.onLoadOlder?.()}
      >
        Load older
      </button>
      <span data-testid="has-more">{String(props.hasMore ?? false)}</span>
      <span data-testid="is-loading-older">
        {String(props.isLoadingOlder ?? false)}
      </span>
      <span data-testid="message-count">{props.messages?.length ?? 0}</span>
    </div>
  ),
}));

vi.mock('@/components/chat/aui/ChatRuntimeProvider', () => ({
  ChatRuntimeProvider: ({ children }: { children: React.ReactNode }) => (
    <section data-testid="chat-runtime">{children}</section>
  ),
}));

vi.mock('@/components/chat/ChatSidebar', () => ({
  ChatSidebar: (props: {
    onSelect: (id: string) => void;
    onNew: () => void;
  }) => (
    <>
      <button
        type="button"
        data-testid="chat-sidebar-select-active"
        onClick={() => props.onSelect('thread-1')}
      >
        Select active thread
      </button>
      <button
        type="button"
        data-testid="chat-sidebar-new"
        onClick={props.onNew}
      >
        New chat
      </button>
      <button
        type="button"
        data-testid="chat-sidebar-select-other"
        onClick={() => props.onSelect('thread-2')}
      >
        Select other thread
      </button>
    </>
  ),
}));

vi.mock('@/hooks/chat/useChatSession', () => ({
  useChatSession: () => mockUseChatSession(),
}));

vi.mock('@/hooks/chat/useChatStreaming', () => ({
  useChatStreaming: () => ({
    input: '',
    setInput: vi.fn(),
    isLoading: false,
    handleSubmit: vi.fn(),
    handleStop: vi.fn(),
    pendingConfirmation: null,
    handleConfirmation: vi.fn(),
    chatInputRef: { current: null },
    storeIsStreaming: false,
    storeStreamingContent: '',
    storeIsRetrievingRag: false,
    streamingThreadId: null,
    selectedModel: 'gpt-4o',
    setSelectedModel: vi.fn(),
  }),
  confirmationBelongsToThread: () => false,
}));

vi.mock('@/hooks/chat/useChatThreadActions', () => ({
  useChatThreadActions: () => ({
    renameDialog: { open: false },
    setRenameDialog: vi.fn(),
    deleteDialog: { open: false },
    setDeleteDialog: vi.fn(),
    bulkDeleteDialog: { open: false },
    setBulkDeleteDialog: vi.fn(),
    handleRenameThread: vi.fn(),
    commitRename: vi.fn(),
    handleDeleteThread: vi.fn(),
    commitDeleteThread: vi.fn(),
    handleBulkDeleteThreads: vi.fn(),
    commitBulkDelete: vi.fn(),
  }),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

describe('ChatPage thread selection', () => {
  beforeEach(() => {
    mockUseChatSession.mockReturnValue({
      conversations: [
        {
          id: 'thread-1',
          title: 'Thread 1',
          messages: [
            { role: 'assistant', content: 'Existing transcript', timestamp: 1 },
          ],
          updatedAt: 1,
        },
        {
          id: 'thread-2',
          title: 'Thread 2',
          messages: [],
          updatedAt: 2,
        },
      ],
      setConversations: vi.fn(),
      activeConversationId: 'thread-1',
      setActiveConversationId: vi.fn(),
      messages: [
        { role: 'assistant', content: 'Existing transcript', timestamp: 1 },
      ],
      setMessages: vi.fn(),
      workspace: { id: 'ws-1', name: 'Workspace' },
      dbConversation: { id: 'conv-1', title: 'Default' },
      isInitializing: false,
      initError: null,
      isLoadingMessages: false,
      activeConversationIdRef: { current: 'thread-1' },
      isHydratedRef: { current: true },
      currentThreadIdFromStore: 'thread-1',
      setCurrentThread: vi.fn(),
      storeMessages: null,
      isAuthenticated: true,
      activeThreadId: 'thread-1',
      displayedMessages: [
        { role: 'assistant', content: 'Existing transcript', timestamp: 1 },
      ],
      loadOlderMessages: vi.fn(),
      messagePagination: null,
      hasMoreThreads: false,
      loadMoreThreads: vi.fn(),
      mapDbMessageToUiMessage: vi.fn(),
      loadThreadsFromDb: vi.fn(),
    });
  });

  it('does not clear the transcript when the active thread is re-selected', () => {
    render(<ChatPage />);

    const selectButtons = screen.getAllByTestId('chat-sidebar-select-active');
    fireEvent.click(selectButtons[0]);

    const session = mockUseChatSession.mock.results[0]?.value as {
      setMessages: ReturnType<typeof vi.fn>;
      setActiveConversationId: ReturnType<typeof vi.fn>;
      setCurrentThread: ReturnType<typeof vi.fn>;
    };

    expect(session.setMessages).not.toHaveBeenCalledWith([]);
    expect(session.setActiveConversationId).not.toHaveBeenCalled();
    expect(session.setCurrentThread).not.toHaveBeenCalled();
  });

  it('routes a sidebar selection only through the Zustand thread authority', () => {
    render(<ChatPage />);

    fireEvent.click(screen.getAllByTestId('chat-sidebar-select-other')[0]);

    const session = mockUseChatSession.mock.results[0]?.value as {
      setMessages: ReturnType<typeof vi.fn>;
      setActiveConversationId: ReturnType<typeof vi.fn>;
      setCurrentThread: ReturnType<typeof vi.fn>;
    };

    expect(session.setCurrentThread).toHaveBeenCalledWith('thread-2');
    expect(session.setActiveConversationId).not.toHaveBeenCalled();
    expect(session.setMessages).not.toHaveBeenCalled();
  });

  it('routes new-chat and command navigation through the same store authority', () => {
    render(<ChatPage />);
    const session = mockUseChatSession.mock.results[0]?.value as {
      setMessages: ReturnType<typeof vi.fn>;
      setActiveConversationId: ReturnType<typeof vi.fn>;
      setCurrentThread: ReturnType<typeof vi.fn>;
    };

    fireEvent.click(screen.getAllByTestId('chat-sidebar-new')[0]);
    expect(session.setCurrentThread).toHaveBeenCalledWith(null);
    expect(session.setActiveConversationId).not.toHaveBeenCalled();
    expect(session.setMessages).not.toHaveBeenCalled();

    session.setCurrentThread.mockClear();
    fireEvent.click(screen.getByTestId('chat-command-open-thread'));
    expect(session.setCurrentThread).toHaveBeenCalledWith('thread-2');
    expect(session.setActiveConversationId).not.toHaveBeenCalled();
    expect(session.setMessages).not.toHaveBeenCalled();
  });

  it('mounts a fresh assistant runtime when the active thread changes', () => {
    const { rerender } = render(<ChatPage />);
    const runtimeForThreadOne = screen.getByTestId('chat-runtime');
    const threadOneSession = mockUseChatSession.mock.results[0]?.value;

    rerender(<ChatPage />);
    expect(screen.getByTestId('chat-runtime')).toBe(runtimeForThreadOne);

    mockUseChatSession.mockReturnValue({
      ...threadOneSession,
      activeConversationId: 'thread-2',
      activeConversationIdRef: { current: 'thread-2' },
      currentThreadIdFromStore: 'thread-2',
      activeThreadId: 'thread-2',
      displayedMessages: [
        { role: 'assistant', content: 'Second transcript', timestamp: 2 },
      ],
    });

    rerender(<ChatPage />);

    expect(screen.getByTestId('chat-runtime')).not.toBe(runtimeForThreadOne);
  });

  it('remounts an empty thread runtime once when its transcript hydrates', () => {
    const emptySession = {
      ...mockUseChatSession(),
      isLoadingMessages: true,
      displayedMessages: [],
    };
    mockUseChatSession.mockReturnValue(emptySession);

    const { rerender } = render(<ChatPage />);
    const emptyRuntime = screen.getByTestId('chat-runtime');

    mockUseChatSession.mockReturnValue({
      ...emptySession,
      isLoadingMessages: false,
      displayedMessages: [
        { role: 'assistant', content: 'Hydrated transcript', timestamp: 2 },
      ],
    });
    rerender(<ChatPage />);

    const hydratedRuntime = screen.getByTestId('chat-runtime');
    expect(hydratedRuntime).not.toBe(emptyRuntime);

    mockUseChatSession.mockReturnValue({
      ...emptySession,
      isLoadingMessages: false,
      displayedMessages: [
        { role: 'assistant', content: 'Hydrated transcript', timestamp: 2 },
        { role: 'user', content: 'Same thread append', timestamp: 3 },
      ],
    });
    rerender(<ChatPage />);

    expect(screen.getByTestId('chat-runtime')).toBe(hydratedRuntime);
  });

  it('announces the transcript loading state', () => {
    mockUseChatSession.mockReturnValue({
      ...mockUseChatSession(),
      isLoadingMessages: true,
      displayedMessages: [],
    });

    render(<ChatPage />);

    expect(
      screen.getByRole('status', { name: 'Loading conversation' })
    ).toBeInTheDocument();
    expect(screen.getByText('Loading conversation')).toBeVisible();
  });

  it('shows the welcome state for a brand-new thread, then the transcript once the first message lands', () => {
    const emptySession = {
      ...mockUseChatSession(),
      activeConversationId: null,
      activeThreadId: null,
      dbConversation: null,
      isLoadingMessages: false,
      displayedMessages: [],
    };
    mockUseChatSession.mockReturnValue(emptySession);

    const { rerender } = render(<ChatPage />);
    expect(screen.getByTestId('welcome-state')).toBeInTheDocument();
    expect(screen.queryByTestId('chat-command-open-thread')).not.toBeInTheDocument();

    mockUseChatSession.mockReturnValue({
      ...emptySession,
      activeConversationId: 'thread-new',
      activeThreadId: 'thread-new',
      displayedMessages: [
        {
          role: 'user',
          content: 'What is retrieval-augmented generation?',
          timestamp: 1,
        },
      ],
    });
    rerender(<ChatPage />);

    expect(screen.queryByTestId('welcome-state')).not.toBeInTheDocument();
    expect(screen.getByTestId('chat-command-open-thread')).toBeInTheDocument();
    expect(screen.getByTestId('message-count')).toHaveTextContent('1');
  });

  it('exposes pagination state without ever replacing the displayed transcript', () => {
    const loadOlderMessages = vi.fn();
    const baseSession = {
      ...mockUseChatSession(),
      activeThreadId: 'thread-1',
      displayedMessages: [
        { role: 'assistant', content: 'Existing transcript', timestamp: 1 },
      ],
      loadOlderMessages,
    };
    mockUseChatSession.mockReturnValue({
      ...baseSession,
      messagePagination: {
        'thread-1': { hasMore: true, loadingOlder: false, loadedCount: 20 },
      },
    });

    const { rerender } = render(<ChatPage />);

    expect(screen.getByTestId('has-more')).toHaveTextContent('true');
    expect(screen.getByTestId('is-loading-older')).toHaveTextContent('false');
    expect(screen.getByTestId('message-count')).toHaveTextContent('1');

    fireEvent.click(screen.getByTestId('load-older'));
    expect(loadOlderMessages).toHaveBeenCalledWith('thread-1');

    // The fetch is now in flight — the flag flips but the already-displayed
    // transcript is never cleared or replaced while older rows load.
    mockUseChatSession.mockReturnValue({
      ...baseSession,
      messagePagination: {
        'thread-1': { hasMore: true, loadingOlder: true, loadedCount: 20 },
      },
    });
    rerender(<ChatPage />);

    expect(screen.getByTestId('is-loading-older')).toHaveTextContent('true');
    expect(screen.getByTestId('message-count')).toHaveTextContent('1');
  });
});
