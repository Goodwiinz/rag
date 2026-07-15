import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ChatPage from '../../../../app/(dashboard)/chat/page';
import {
  selectDisplayedMessages,
  type ChatPageMessage,
} from '@/components/chat/shared/cloudMessageView';
import type { ChatMessage } from '@/types/workspace';
import { makeChatPageMessage } from '@/test/chatMessageFactory';

const mockUseChatSession = vi.fn();

vi.mock('@/components/chat', () => ({
  ChatInput: () => <div data-testid="chat-input" />,
  CitationPanel: () => null,
  WelcomeState: () => <div data-testid="welcome-state" />,
}));
vi.mock('@/components/chat/ChatDialogs', () => ({ ChatDialogs: () => null }));
vi.mock('@/components/chat/ChatHeader', () => ({ ChatHeader: () => null }));
vi.mock('@/components/chat/ChatMessageList', () => ({
  ChatMessageList: ({ messages }: { messages: ChatPageMessage[] }) => (
    <div>
      {messages.map((message) => (
        <p key={`${message.role}:${message.content}`}>{message.content}</p>
      ))}
    </div>
  ),
}));
vi.mock('@/components/chat/aui/ChatRuntimeProvider', () => ({
  ChatRuntimeProvider: ({ children }: { children: React.ReactNode }) =>
    children,
}));
vi.mock('@/components/chat/ChatSidebar', () => ({ ChatSidebar: () => null }));
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
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));

const QUERY = 'Find recent arXiv papers on retrieval-augmented generation';

function persisted(
  id: string,
  role: 'user' | 'assistant',
  content: string,
  createdAt: string
): ChatMessage {
  return {
    id,
    thread_id: 'thread-A',
    role,
    content,
    created_at: createdAt,
  } as ChatMessage;
}

function session(
  localMessages: ChatPageMessage[],
  storeMessages: ChatMessage[]
) {
  return {
    conversations: [
      { id: 'thread-A', title: 'A', messages: localMessages, updatedAt: 1 },
    ],
    setConversations: vi.fn(),
    activeConversationId: 'thread-A',
    setActiveConversationId: vi.fn(),
    messages: localMessages,
    setMessages: vi.fn(),
    workspace: { id: 'ws-1', name: 'Workspace' },
    dbConversation: { id: 'conv-1', title: 'Default' },
    isInitializing: false,
    initError: null,
    isLoadingMessages: false,
    activeConversationIdRef: { current: 'thread-A' },
    isHydratedRef: { current: true },
    currentThreadIdFromStore: 'thread-A',
    setCurrentThread: vi.fn(),
    storeMessages,
    addMessageToStore: vi.fn(),
    isAuthenticated: true,
    activeThreadId: 'thread-A',
    displayedMessages: selectDisplayedMessages({
      localMessages,
      storeMessages,
    }),
    loadOlderMessages: vi.fn(),
    messagePagination: null,
    hasMoreThreads: false,
    loadMoreThreads: vi.fn(),
    mapDbMessageToUiMessage: vi.fn(),
    loadThreadsFromDb: vi.fn(),
  };
}

describe('ChatPage completed-turn persistence', () => {
  beforeEach(() => vi.clearAllMocks());

  it('keeps a completed turn visible while an equal-length canonical cache is stale', () => {
    const localMessages: ChatPageMessage[] = [
      makeChatPageMessage({
        id: 'old-user',
        role: 'user',
        content: 'Earlier question',
        timestamp: 1,
      }),
      makeChatPageMessage({
        id: 'old-assistant',
        role: 'assistant',
        content: 'Earlier answer',
        timestamp: 2,
      }),
      makeChatPageMessage({ role: 'user', content: QUERY, timestamp: 3 }),
      makeChatPageMessage({
        id: 'new-assistant',
        runtimeId: 'runtime-new-assistant',
        source: 'optimistic',
        role: 'assistant',
        content: 'Five recent papers',
        timestamp: 4,
      }),
    ];
    const staleCanonical = [
      persisted('old-user', 'user', 'Earlier question', '2026-07-15T00:00:00Z'),
      persisted(
        'old-assistant',
        'assistant',
        'Earlier answer',
        '2026-07-15T00:00:01Z'
      ),
      persisted(
        'stale-user',
        'user',
        'A different cached question',
        '2026-07-15T00:00:02Z'
      ),
      persisted(
        'stale-assistant',
        'assistant',
        'A different cached answer',
        '2026-07-15T00:00:03Z'
      ),
    ];
    mockUseChatSession.mockReturnValue(session(localMessages, staleCanonical));

    render(<ChatPage />);

    expect(screen.getByText(QUERY)).toBeVisible();
    expect(screen.getByText('Five recent papers')).toBeVisible();
  });
});
