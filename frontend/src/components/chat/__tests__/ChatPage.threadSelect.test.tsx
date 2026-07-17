import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ChatPage from '../../../../app/(dashboard)/chat/page';

const mockUseChatSession = vi.fn();
const sidebarPropsRef: { current: Record<string, unknown> | null } = {
  current: null,
};

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
  ChatMessageList: () => <div data-testid="chat-message-list" />,
}));

vi.mock('@/components/chat/ChatSidebar', () => ({
  ChatSidebar: (props: Record<string, unknown>) => {
    sidebarPropsRef.current = props;
    return (
      <button
        type="button"
        data-testid="chat-sidebar-select-active"
        onClick={() => (props.onSelect as (id: string) => void)('thread-1')}
      >
        Select active thread
      </button>
    );
  },
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
    sidebarPropsRef.current = null;
    mockUseChatSession.mockReturnValue({
      conversations: [
        {
          id: 'thread-1',
          title: 'Thread 1',
          messages: [
            {
              role: 'assistant',
              content: 'Existing transcript',
              timestamp: 1,
            },
          ],
          updatedAt: 1,
        },
      ],
      setConversations: vi.fn(),
      activeConversationId: 'thread-1',
      setActiveConversationId: vi.fn(),
      messages: [
        {
          role: 'assistant',
          content: 'Existing transcript',
          timestamp: 1,
        },
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
      addMessageToStore: vi.fn(),
      isAuthenticated: true,
      activeThreadId: 'thread-1',
      displayedMessages: [
        {
          role: 'assistant',
          content: 'Existing transcript',
          timestamp: 1,
        },
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

    fireEvent.click(screen.getByTestId('chat-sidebar-select-active'));

    const session = mockUseChatSession.mock.results[0]?.value as {
      setMessages: ReturnType<typeof vi.fn>;
      setActiveConversationId: ReturnType<typeof vi.fn>;
      setCurrentThread: ReturnType<typeof vi.fn>;
    };

    expect(session.setMessages).not.toHaveBeenCalledWith([]);
    expect(session.setActiveConversationId).not.toHaveBeenCalled();
    expect(session.setCurrentThread).not.toHaveBeenCalled();
  });
});
