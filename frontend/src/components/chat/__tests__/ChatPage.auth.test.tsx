import { render, screen } from '@testing-library/react';
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
  ChatMessageList: () => <div data-testid="chat-message-list" />,
}));

vi.mock('@/components/chat/ChatSidebar', () => ({
  ChatSidebar: () => <div data-testid="chat-sidebar" />,
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
    isConfirming: false,
    handleConfirmation: vi.fn(),
    chatInputRef: { current: null },
    storeIsStreaming: false,
    storeStreamingContent: '',
    streamingTimestampRef: { current: null },
    selectedModel: 'gpt-4o',
    setSelectedModel: vi.fn(),
  }),
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

describe('ChatPage auth states', () => {
  beforeEach(() => {
    mockUseChatSession.mockReturnValue({
      conversations: [],
      setConversations: vi.fn(),
      activeConversationId: null,
      setActiveConversationId: vi.fn(),
      messages: [],
      setMessages: vi.fn(),
      workspace: null,
      dbConversation: null,
      isInitializing: false,
      isAuthLoading: true,
      initError: null,
      isLoadingMessages: false,
      activeConversationIdRef: { current: null },
      isHydratedRef: { current: false },
      currentThreadIdFromStore: null,
      setCurrentThread: vi.fn(),
      storeMessages: {},
      addMessageToStore: vi.fn(),
      isAuthenticated: false,
      activeThreadId: null,
      displayedMessages: [],
      mapDbMessageToUiMessage: vi.fn(),
      loadThreadsFromDb: vi.fn(),
    });
  });

  it('keeps showing the loading state while authentication is still initializing', () => {
    render(<ChatPage />);

    expect(screen.getByText('Initializing...')).toBeInTheDocument();
    expect(
      screen.queryByText('Authentication required. Redirecting...')
    ).not.toBeInTheDocument();
  });
});
